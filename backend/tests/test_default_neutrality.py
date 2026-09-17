"""v0.5.1 默认体验中立性契约（开源观感清洗）

锁定「新用户第一次运行」时的默认行为：
- 默认 General Assistant 零采集字段、ASK 模式，公开挂件配置不下发任何采集字段；
- 默认系统提示词 / 欢迎语不含销售式话术（不索取姓名、电话、联系方式）；
- Lead Generation 能力本身不删除：sales 模板仍为 collect + data_type=lead，
  只是不再作为默认行为出现。
"""
import pytest

from app.services import assistant_store
from app.services.config_store import DEFAULT_CONFIG, get_all_config

pytestmark = pytest.mark.asyncio(loop_scope="session")

# 默认话术中不应出现的销售式引导词
_SALES_WORDS = ["留资", "获客", "销售线索", "联系方式", "手机号", "留下", "顾问", "报价意向"]


async def test_global_defaults_are_field_free_and_neutral():
    # 全局默认：零采集字段 + 中立话术
    assert DEFAULT_CONFIG["business_fields"] == []
    prompt = DEFAULT_CONFIG["system_prompt"]
    welcome = DEFAULT_CONFIG["welcome_message"]
    for word in _SALES_WORDS:
        assert word not in prompt, f"默认系统提示词不应出现「{word}」"
        assert word not in welcome, f"默认欢迎语不应出现「{word}」"
    assert "{company_name}" in prompt  # 默认提示词仍是可渲染的完整模板


async def test_runtime_default_assistant_has_no_fields(db):
    # 默认助手无字段行 → 回退全局 business_fields；而全局默认为空数组
    from app.services import business_fields

    default = await assistant_store.ensure_default_assistant(db)
    global_cfg = await get_all_config(db)
    fields = await business_fields.get_runtime_fields(db, default, global_cfg)
    assert fields == []
    assert assistant_store.get_collect_config(default)["mode"] == "ask"
    assert assistant_store.get_collect_config(default)["data_type"] == "custom"


async def test_widget_config_exposes_no_capture_fields(client):
    resp = await client.get("/api/widget/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_id"] == "default"
    assert data["collect_mode"] == "ask"
    # 公开配置不得下发任何采集字段（姓名 / 电话 / 邮箱 / 需求…）
    assert data["business_fields"] == []
    for word in _SALES_WORDS:
        assert word not in data["welcome_message"]


async def test_general_template_is_pure_qa(client, admin_headers):
    resp = await client.get("/api/assistants/templates", headers=admin_headers)
    scenarios = {s["key"]: s for s in resp.json()["scenarios"]}
    general = scenarios["general"]
    assert general["collect"]["mode"] == "ask"
    assert general["fields"] == []
    for word in _SALES_WORDS:
        assert word not in general["system_prompt"]


async def test_lead_generation_capability_retained_but_opt_in(client, admin_headers):
    # sales 模板仍是完整的 Lead Generation 能力（可选项，非默认）
    resp = await client.get("/api/assistants/templates", headers=admin_headers)
    scenarios = {s["key"]: s for s in resp.json()["scenarios"]}
    sales = scenarios["sales"]
    assert sales["collect"]["mode"] == "collect"
    assert sales["collect"]["data_type"] == "lead"
    assert {f["key"] for f in sales["fields"]} >= {"name", "phone"}

    # 显式创建销售助手后，其运行时字段才会下发
    await client.post("/api/assistants", headers=admin_headers, json={
        "id": "lead-opt-in", "name": "销售助手", "scenario": "sales",
    })
    resp = await client.get("/api/widget/config?assistant=lead-opt-in")
    data = resp.json()
    assert data["assistant_id"] == "lead-opt-in"
    assert data["collect_mode"] == "collect"
    assert "name" in [f["key"] for f in data["business_fields"]]
