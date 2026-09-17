"""助手管理接口 + 挂件配置解析的端到端测试"""
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_admin_endpoints_require_auth(client):
    assert (await client.get("/api/assistants")).status_code == 401
    assert (await client.get("/api/assistants/templates")).status_code == 401
    assert (await client.get("/api/collected-data")).status_code == 401
    # 挂件配置保持公开
    assert (await client.get("/api/widget/config")).status_code == 200


async def test_scenario_templates(client, admin_headers):
    resp = await client.get("/api/assistants/templates", headers=admin_headers)
    assert resp.status_code == 200
    scenarios = {s["key"]: s for s in resp.json()["scenarios"]}
    assert set(scenarios) == {"general", "support", "internal", "requirement", "sales"}
    # 展示顺序：通用 → 客服 → 内部 → 需求 → 销售（销售置末）
    assert [s["key"] for s in resp.json()["scenarios"]] == [
        "general", "support", "internal", "requirement", "sales"
    ]
    # 默认场景 general：纯问答
    assert scenarios["general"]["collect"]["mode"] == "ask"
    assert scenarios["general"]["collect"]["data_type"] == "custom"
    assert scenarios["general"]["fields"] == []
    # 售后工单
    support = scenarios["support"]
    assert support["collect"]["data_type"] == "ticket"
    assert support["collect"]["mode"] == "collect"
    assert any(f["key"] == "order_id" for f in support["fields"])
    assert "system_prompt" in support and "context" in support and "ui" in support
    # internal 仅答疑；requirement/sales 采集但数据类型不同
    assert scenarios["internal"]["collect"]["mode"] == "ask"
    assert scenarios["requirement"]["collect"]["data_type"] == "requirement"
    assert scenarios["sales"]["collect"]["data_type"] == "lead"


async def test_default_assistant_seeded(client, admin_headers):
    resp = await client.get("/api/assistants", headers=admin_headers)
    rows = {a["id"]: a for a in resp.json()["assistants"]}
    assert "default" in rows
    d = rows["default"]
    assert d["is_default"] is True and d["status"] == "active"
    # v0.5：默认助手是通用问答助手（general / ask / custom），不含销售预设
    assert d["scenario"] == "general"
    assert d["collect_config"]["mode"] == "ask"
    assert d["collect_config"]["data_type"] == "custom"
    # 默认助手不复制字段：运行时回退全局 business_fields
    assert d["business_fields"] == []


async def test_crud_and_validation(client, admin_headers):
    # 非法 ID → 400（服务层 slug 校验）
    resp = await client.post("/api/assistants", headers=admin_headers,
                             json={"id": "Bad ID!", "name": "非法ID", "scenario": "general"})
    assert resp.status_code == 400

    # 重复 ID → 400（default 已由播种存在）
    resp = await client.post("/api/assistants", headers=admin_headers,
                             json={"id": "default", "name": "重复ID", "scenario": "general"})
    assert resp.status_code == 400

    # 不存在 → 404
    assert (await client.get("/api/assistants/missing", headers=admin_headers)).status_code == 404

    # 创建（场景模板预填字段）
    resp = await client.post("/api/assistants", headers=admin_headers, json={
        "id": "qa-assist", "name": "问答助手", "scenario": "general",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "qa-assist" and body["is_default"] is False
    assert body["status"] == "active" and body["system_prompt"]  # 模板话术已预填

    # 从 support 模板创建：字段与采集类型一并落库
    resp = await client.post("/api/assistants", headers=admin_headers, json={
        "id": "aftersales", "name": "售后", "scenario": "support",
    })
    assert resp.status_code == 201
    fields = {f["key"]: f for f in resp.json()["business_fields"]}
    assert {"order_id", "issue_type"} <= set(fields)
    assert fields["issue_type"]["type"] == "enum" and fields["issue_type"]["options"]

    # 更新
    resp = await client.put("/api/assistants/qa-assist", headers=admin_headers,
                            json={"name": "新名字", "status": "disabled"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "新名字" and resp.json()["status"] == "disabled"

    # 切默认再切回
    resp = await client.put("/api/assistants/qa-assist/default", headers=admin_headers)
    assert resp.status_code == 200 and resp.json()["is_default"] is True
    # 设默认会自动启用
    assert resp.json()["status"] == "active"
    resp = await client.put("/api/assistants/default/default", headers=admin_headers)
    assert resp.json()["is_default"] is True

    # 默认助手不可删
    assert (await client.delete("/api/assistants/default", headers=admin_headers)).status_code == 400
    # 普通助手可删，删后 404
    assert (await client.delete("/api/assistants/qa-assist", headers=admin_headers)).status_code == 200
    assert (await client.get("/api/assistants/qa-assist", headers=admin_headers)).status_code == 404


async def test_widget_config_assistant_resolution(client, admin_headers):
    # 默认配置：公开可读
    resp = await client.get("/api/widget/config")
    assert resp.status_code == 200
    assert resp.json()["assistant_id"] == "default"
    assert resp.json()["company_name"] == "LeadChat"
    # 默认助手为 ASK 模式
    assert resp.json()["collect_mode"] == "ask"

    # 新建带 UI 覆盖的助手
    resp = await client.post("/api/assistants", headers=admin_headers, json={
        "id": "ui-demo", "name": "外观演示", "scenario": "support",
        "ui_config": {"title": "售后小助手", "theme": "#10B981", "position": "left"},
    })
    assert resp.status_code == 201

    resp = await client.get("/api/widget/config?assistant=ui-demo")
    data = resp.json()
    assert data["assistant_id"] == "ui-demo"
    assert data["company_name"] == "售后小助手"
    assert data["widget_theme"] == "#10B981"
    assert data["widget_position"] == "left"
    assert data["collect_mode"] == "collect"  # support 场景
    # 未覆盖的欢迎语继承全局
    assert data["welcome_message"]

    # 停用后流量回退默认助手
    await client.put("/api/assistants/ui-demo", headers=admin_headers, json={"status": "disabled"})
    resp = await client.get("/api/widget/config?assistant=ui-demo")
    assert resp.json()["assistant_id"] == "default"

    # 不存在的 ID 同样回退
    resp = await client.get("/api/widget/config?assistant=ghost")
    assert resp.json()["assistant_id"] == "default"
