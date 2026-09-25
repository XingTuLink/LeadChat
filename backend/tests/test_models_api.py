"""模型管理接口测试（多模型在线切换）

覆盖：
- GET  /api/models/providers 厂商列表
- GET  /api/models 列表中 Key 必须掩码
- POST /api/models 创建
- POST /api/models/{id}/activate 激活唯一
- PUT  /api/models/{id} 空 Key 不覆盖原 Key
- POST /api/models/{id}/test 连通性测试（打桩 LLM）
- DELETE /api/models/{id}
- 无激活模型时对话链路给出友好提示，恢复后正常
"""
import json

import pytest

from app.services import model_store

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_providers_listed(client, admin_headers):
    resp = await client.get("/api/models/providers", headers=admin_headers)
    assert resp.status_code == 200
    keys = [p["key"] for p in resp.json()["providers"]]
    assert keys == ["openai", "deepseek", "qwen", "glm", "ollama", "custom"]


async def test_list_masks_api_key(client, admin_headers):
    resp = await client.get("/api/models", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    by_id = {m["id"]: m for m in data["models"]}
    seeded = by_id["test-active-model"]
    assert seeded["is_active"] is True
    # 原始 Key sk-test-1234567890abcdef 不得原样返回
    assert seeded["api_key"] != "sk-test-1234567890abcdef"
    assert "*" in seeded["api_key"]
    assert seeded["api_key"].startswith("sk-t")


async def test_create_and_activate(client, admin_headers):
    # 创建一个未激活模型
    resp = await client.post("/api/models", headers=admin_headers, json={
        "id": "second-model", "name": "第二模型", "provider": "deepseek",
        "model_name": "deepseek-chat", "api_key": "sk-second-1234567890",
        "api_base": "", "is_active": False,
    })
    assert resp.status_code == 201
    assert resp.json()["is_active"] is False

    # 激活：旧模型应同时被取消激活，全局唯一
    resp = await client.post(
        "/api/models/second-model/activate", headers=admin_headers
    )
    assert resp.status_code == 200
    listing = await client.get("/api/models", headers=admin_headers)
    actives = [m for m in listing.json()["models"] if m["is_active"]]
    assert len(actives) == 1
    assert actives[0]["id"] == "second-model"


async def test_update_empty_key_keeps_original(client, admin_headers):
    # 不传 api_key：原 Key 必须保留
    await client.put("/api/models/second-model", headers=admin_headers, json={
        "name": "第二模型改名",
    })
    # 通过服务层读取未掩码值验证
    from app.models.llm_model import LLMModel

    async with _session() as s:
        row = await s.get(LLMModel, "second-model")
        assert row.api_key == "sk-second-1234567890"
        assert row.name == "第二模型改名"


async def test_update_with_masked_key_ignored(client, admin_headers):
    # 把列表里的掩码原样回传，也不应覆盖原 Key
    listing = await client.get("/api/models", headers=admin_headers)
    masked = next(
        m["api_key"] for m in listing.json()["models"] if m["id"] == "second-model"
    )
    await client.put("/api/models/second-model", headers=admin_headers, json={
        "api_key": masked,
    })
    from app.models.llm_model import LLMModel

    async with _session() as s:
        row = await s.get(LLMModel, "second-model")
        assert row.api_key == "sk-second-1234567890"


async def test_test_endpoint_success(client, admin_headers, monkeypatch):
    async def fake_chat(messages, **kwargs):
        return "pong"

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)
    resp = await client.post(
        "/api/models/second-model/test", headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["reply"] == "pong"


async def test_test_endpoint_failure(client, admin_headers, monkeypatch):
    async def broken_chat(messages, **kwargs):
        raise RuntimeError("401 invalid key")

    monkeypatch.setattr("app.services.llm.chat_completion", broken_chat)
    resp = await client.post(
        "/api/models/second-model/test", headers=admin_headers
    )
    assert resp.status_code == 400
    assert "401 invalid key" in resp.json()["detail"]


async def test_delete_model(client, admin_headers):
    resp = await client.delete("/api/models/second-model", headers=admin_headers)
    assert resp.status_code == 200
    listing = await client.get("/api/models", headers=admin_headers)
    assert all(m["id"] != "second-model" for m in listing.json()["models"])


async def test_chat_fails_without_active_model(client, admin_headers, monkeypatch):
    """无激活模型：非流式友好提示 + 流式 error 事件；结束后恢复激活模型"""
    # 当前 second-model 已删除，激活 test-active-model
    await client.post(
        "/api/models/test-active-model/activate", headers=admin_headers
    )
    from sqlalchemy import update as sa_update

    from app.database import AsyncSessionLocal
    from app.models.llm_model import LLMModel

    async with AsyncSessionLocal() as s:
        await s.execute(sa_update(LLMModel).values(is_active=False))
        await s.commit()

    try:
        # 非流式：返回友好文案，不抛 500
        resp = await client.post("/api/chat/message", json={"message": "你好"})
        assert resp.status_code == 200
        assert "尚未配置完成" in resp.json()["reply"]

        # 流式：首个事件即 error
        async with client.stream(
            "POST", "/api/chat/message/stream", json={"message": "你好"}
        ) as r:
            raw = (await r.aread()).decode("utf-8")
        assert "event: error" in raw
        data_line = [
            l for l in raw.split("\n") if l.startswith("data:")
        ][0]
        assert json.loads(data_line[5:].strip())["message"]
    finally:
        # 恢复激活模型，保证后续/其他测试不受影响
        await client.post(
            "/api/models/test-active-model/activate", headers=admin_headers
        )


# ------------------------------------------------------------------ 工具

def _session():
    from app.database import AsyncSessionLocal

    return AsyncSessionLocal()
