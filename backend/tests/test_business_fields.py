"""Business Fields 存储层：key 规范化、枚举选项、默认助手全局字段回退"""
import pytest

from app.services import assistant_store, business_fields
from app.services.config_store import get_all_config

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_apply_fields_key_normalization_and_dedup(db):
    assistant = await assistant_store.create_assistant(db, {
        "id": "field-test",
        "name": "字段测试",
        "scenario": "general",
        "business_fields": [
            {"key": "Order_ID", "label": "订单号", "type": "string", "required": True},
            {"key": "order_id", "label": "重复键", "type": "string"},  # 与上者规范化后重复 → 丢弃
            {"key": "issue_type", "label": "问题类型", "type": "enum",
             "options": ["报修", "退换货"], "required": True},
            {"key": "contact", "label": "联系电话", "type": "phone"},
        ],
    })
    rows = await assistant_store.list_fields(db, assistant.id)
    keys = [r.field_key for r in rows]
    assert keys == ["order_id", "issue_type", "contact"]

    detail = await assistant_store.assistant_to_dict(db, assistant)
    by_key = {f["key"]: f for f in detail["business_fields"]}
    assert by_key["order_id"]["required"] is True
    assert by_key["issue_type"]["type"] == "enum"
    assert by_key["issue_type"]["options"] == ["报修", "退换货"]
    assert by_key["contact"]["type"] == "phone"


async def test_runtime_fields_fallback_chain(db):
    # v0.5.1：默认助手无 business_fields 行，全局 business_fields 默认为空 → 运行时零字段
    default = await assistant_store.ensure_default_assistant(db)
    global_cfg = await get_all_config(db)
    assert global_cfg["business_fields"] == []
    fields = await business_fields.get_runtime_fields(db, default, global_cfg)
    assert fields == []

    # 管理员显式配置全局字段后，默认助手通过回退继承（name/phone 质量校验照常生效）
    global_cfg["business_fields"] = [
        {"key": "name", "label": "姓名", "type": "string", "required": True},
        {"key": "phone", "label": "电话", "type": "phone", "required": True},
        {"key": "wechat", "label": "微信号", "required": False},
    ]
    fields2 = await business_fields.get_runtime_fields(db, default, global_cfg)
    by_key = {f["key"]: f for f in fields2}
    assert set(by_key) == {"name", "phone", "wechat"}
    assert by_key["name"]["type"] == "string" and by_key["phone"]["type"] == "phone"

    # 非默认助手且未配置字段 → 空列表（不回退全局字段）
    other = await assistant_store.create_assistant(db, {
        "id": "empty-fields", "name": "无字段", "scenario": "general", "business_fields": []
    })
    assert await business_fields.get_runtime_fields(db, other, global_cfg) == []
