"""通用业务数据采集回归（LLM/RAG 全部打桩，不发网络请求）

v0.5 Assistant-first 迁移后覆盖：
- 销售线索只是 data_type=lead 的一种采集结果（不再有 leads 表/接口/双写）
- 售后工单（ticket）、需求收集（requirement）与 lead 走同一条链路
- ask 模式（默认 general 助手）不采集
- 旧挂件请求（无 assistant_id/context）行为不变
- Web Context 白名单持久化
- 全局 business_fields 对默认助手继续生效
- 采集数据状态流转 + 删除对话解绑
- /api/leads 已移除（404），统计字段更名为 *_collected
"""
import json

import pytest
from sqlalchemy import select

from app.models.conversation import Conversation

pytestmark = pytest.mark.asyncio(loop_scope="session")


def install_fake_llm(monkeypatch, extracted, has_intent=True, reply="好的，信息我都记下来了。"):
    """打桩 LLM：抽取调用（temperature=0.0）返回字段 JSON，其余返回普通回复"""
    state = {"extract_calls": 0}

    async def fake_chat(messages, **kwargs):
        if kwargs.get("temperature") == 0.0:
            state["extract_calls"] += 1
            return json.dumps({"has_intent": has_intent, "fields": extracted}, ensure_ascii=False)
        return reply

    monkeypatch.setattr("app.services.llm.chat_completion", fake_chat)
    return state


@pytest.fixture(autouse=True)
def _patch_externals(monkeypatch):
    async def fake_rag_search(*args, **kwargs):
        return []

    monkeypatch.setattr("app.services.rag.search", fake_rag_search)


async def _new_conversation(client, **payload):
    resp = await client.post("/api/chat/conversation", json=payload or {})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_sales_lead_is_just_a_data_type(client, admin_headers, monkeypatch):
    # sales 只是 5 个场景之一：需显式创建销售助手，默认助手不再是销售
    await client.post("/api/assistants", headers=admin_headers, json={
        "id": "lead-bot", "name": "销售助手", "scenario": "sales",
    })
    conv = await _new_conversation(client, assistant_id="lead-bot")
    assert conv["assistant_id"] == "lead-bot"

    install_fake_llm(monkeypatch, {
        "name": "张三", "phone": "13800000000", "email": None, "requirement": "企业版报价",
    })
    resp = await client.post("/api/chat/message", json={
        "conversation_id": conv["conversation_id"],
        "message": "我想购买企业版，我是张三，电话13800000000",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["assistant_id"] == "lead-bot"
    assert data["data_captured"] is True
    assert data["data_type"] == "lead"
    # 旧的 lead_captured 字段已随干净迁移移除
    assert "lead_captured" not in data

    # lead 仅作为 collected_data 的一种类型存在
    resp = await client.get("/api/collected-data?data_type=lead", headers=admin_headers)
    item = next(i for i in resp.json()["items"]
                if i["conversation_id"] == conv["conversation_id"])
    assert item["assistant_id"] == "lead-bot"
    assert item["payload"]["name"] == "张三" and item["payload"]["phone"] == "13800000000"

    # 同一会话不重复采集
    resp = await client.post("/api/chat/message", json={
        "conversation_id": conv["conversation_id"], "message": "再问个问题",
    })
    assert resp.json()["data_captured"] is False
    assert resp.json()["data_type"] is None


async def test_lead_endpoint_removed(client):
    # v0.5：独立的线索接口已删除，销售线索统一走 /api/collected-data?data_type=lead
    assert (await client.get("/api/leads")).status_code == 404
    assert (await client.post("/api/leads", json={})).status_code == 404


async def test_ticket_captured_and_unbind_on_delete(client, admin_headers, monkeypatch):
    await client.post("/api/assistants", headers=admin_headers, json={
        "id": "ticket-bot", "name": "工单助手", "scenario": "support",
    })
    conv = await _new_conversation(client, assistant_id="ticket-bot")
    assert conv["assistant_id"] == "ticket-bot"

    install_fake_llm(monkeypatch, {
        "order_id": "O-20260917-001",
        "issue_type": "故障报修",
        "phone": None,
        "issue_detail": None,
    })
    resp = await client.post("/api/chat/message", json={
        "conversation_id": conv["conversation_id"],
        "message": "我的订单 O-20260917-001 设备开不了机，需要故障报修",
    })
    data = resp.json()
    assert data["data_captured"] is True
    assert data["data_type"] == "ticket"

    # 工单进入采集表并可按类型+助手过滤
    resp = await client.get(
        "/api/collected-data?data_type=ticket&assistant_id=ticket-bot", headers=admin_headers
    )
    body = resp.json()
    assert body["total"] >= 1
    item = body["items"][0]
    assert item["payload"]["order_id"] == "O-20260917-001"
    assert item["payload"]["issue_type"] == "故障报修"
    item_id = item["id"]

    # 状态流转
    assert (await client.put(f"/api/collected-data/{item_id}", headers=admin_headers,
                             json={"status": "processed"})).status_code == 200
    bad = await client.put(f"/api/collected-data/{item_id}", headers=admin_headers,
                           json={"status": "weird"})
    assert bad.status_code == 422

    # 删除对话：采集记录保留但解绑 conversation_id
    assert (await client.delete(
        f"/api/chat/conversations/{conv['conversation_id']}", headers=admin_headers
    )).status_code == 200
    rows = (await client.get("/api/collected-data?data_type=ticket", headers=admin_headers)).json()["items"]
    kept = next(i for i in rows if i["id"] == item_id)
    assert kept["conversation_id"] is None


async def test_requirement_captured_with_optional_contacts(client, admin_headers, monkeypatch):
    # requirement 场景仅「需求描述」必填：不留姓名电话也能落库
    await client.post("/api/assistants", headers=admin_headers, json={
        "id": "req-bot", "name": "需求助手", "scenario": "requirement",
    })
    conv = await _new_conversation(client, assistant_id="req-bot")

    install_fake_llm(monkeypatch, {
        "requirement": "需要一套库存管理系统，支持多仓库",
        "name": None, "phone": None,
    })
    resp = await client.post("/api/chat/message", json={
        "conversation_id": conv["conversation_id"],
        "message": "我想做个库存管理系统，有多个仓库要同步",
    })
    data = resp.json()
    assert data["data_captured"] is True
    assert data["data_type"] == "requirement"

    resp = await client.get(
        "/api/collected-data?data_type=requirement&assistant_id=req-bot", headers=admin_headers
    )
    item = next(i for i in resp.json()["items"]
                if i["conversation_id"] == conv["conversation_id"])
    assert "库存管理系统" in item["payload"]["requirement"]
    assert "name" not in item["payload"] and "phone" not in item["payload"]


async def test_ask_mode_never_captures(client, admin_headers, monkeypatch):
    await client.post("/api/assistants", headers=admin_headers, json={
        "id": "faq-bot", "name": "通用问答", "scenario": "general",
    })
    conv = await _new_conversation(client, assistant_id="faq-bot")

    state = install_fake_llm(monkeypatch, extracted={})
    resp = await client.post("/api/chat/message", json={
        "conversation_id": conv["conversation_id"], "message": "你们产品支持 SSO 吗？",
    })
    assert resp.json()["data_captured"] is False
    assert resp.json()["data_type"] is None
    # ASK 模式不发起抽取调用
    assert state["extract_calls"] == 0

    resp = await client.get(
        "/api/collected-data?assistant_id=faq-bot", headers=admin_headers
    )
    assert resp.json()["total"] == 0


async def test_legacy_widget_requests_unchanged(client, monkeypatch):
    # 旧挂件：无 conversation_id / assistant_id / context，仍 200 且落到默认助手
    install_fake_llm(monkeypatch, extracted={}, has_intent=False)
    resp = await client.post("/api/chat/message", json={"message": "你好"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_id"] == "default"
    assert data["data_captured"] is False
    assert data["reply"] == "好的，信息我都记下来了。"

    # 不存在的助手回退默认助手
    resp = await client.post("/api/chat/message", json={
        "message": "在吗", "assistant_id": "ghost",
    })
    assert resp.json()["assistant_id"] == "default"

    # context 入口粗校验：嵌套值拒绝 422
    resp = await client.post("/api/chat/message", json={
        "message": "查订单", "context": {"order": {"id": "O-1"}},
    })
    assert resp.status_code == 422


async def test_context_sanitized_and_persisted(client, db, admin_headers):
    await client.post("/api/assistants", headers=admin_headers, json={
        "id": "ctx-bot", "name": "上下文助手", "scenario": "support",
    })
    # support 白名单：page / user_id / order_id / product_model；secret 应被丢弃
    resp = await client.post("/api/chat/conversation", json={
        "assistant_id": "ctx-bot",
        "context": {"page": "/ticket", "order_id": "O-7", "secret": "should-not-pass"},
    })
    cid = resp.json()["conversation_id"]

    await db.rollback()  # 确保读到 API 已提交的数据
    conv = (await db.execute(select(Conversation).where(Conversation.id == cid))).scalar_one()
    stored = json.loads(conv.context_json)
    assert stored == {"page": "/ticket", "order_id": "O-7"}
    assert conv.assistant_id == "ctx-bot"


async def test_global_business_fields_in_widget_config(client, admin_headers):
    # 全局配置键已更名为 business_fields，默认助手公开配置中可见
    original = (await client.get("/api/config", headers=admin_headers)).json()["config"]["business_fields"]
    try:
        custom_fields = [
            {"key": "name", "label": "姓名", "type": "string", "required": True},
            {"key": "company", "label": "公司名称", "type": "string", "required": True},
        ]
        resp = await client.put("/api/config", headers=admin_headers, json={
            "key": "business_fields", "value": custom_fields,
        })
        assert resp.status_code == 200

        resp = await client.get("/api/widget/config")
        keys = [f["key"] for f in resp.json()["business_fields"]]
        assert "company" in keys
        # 旧键名不再下发
        assert "lead_form_fields" not in resp.json()
    finally:
        await client.put("/api/config", headers=admin_headers,
                         json={"key": "business_fields", "value": original})


async def test_stats_uses_collected_field_names(client, admin_headers):
    resp = await client.get("/api/chat/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "today_collected" in data and "total_collected" in data
    assert "today_leads" not in data and "total_leads" not in data
