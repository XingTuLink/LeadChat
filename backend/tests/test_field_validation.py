"""Business Fields 纯函数单元测试（无需 DB / 事件循环）"""
from app.services import business_fields


def test_normalize_field_types_and_options():
    f = business_fields.normalize_field(
        {"key": "qty", "label": "数量", "type": "weird", "options": ["a", " ", 3], "required": 1}
    )
    assert f["type"] == "string"  # 非法类型回退 string
    assert f["options"] == ["a", "3"]
    assert f["required"] is True

    f2 = business_fields.normalize_field({"key": "k"})
    assert f2["label"] == "k" and f2["options"] == [] and f2["required"] is False


def test_clean_value_quality_gates():
    assert business_fields.clean_value({"key": "phone", "type": "phone"}, "我的电话是13800000000") == "13800000000"
    assert business_fields.clean_value({"key": "phone", "type": "phone"}, "123") is None
    assert business_fields.clean_value({"key": "email", "type": "email"}, "邮箱 a@b.com 谢谢") == "a@b.com"
    assert business_fields.clean_value({"key": "email", "type": "email"}, "not-an-email") is None
    assert business_fields.clean_value({"key": "qty", "type": "number"}, "数量 42 台") == "42"

    enum_field = {"key": "issue_type", "type": "enum", "options": ["使用咨询", "故障报修", "退换货"]}
    assert business_fields.clean_value(enum_field, "我要故障报修") == "故障报修"
    assert business_fields.clean_value(enum_field, "随便聊聊") is None

    assert business_fields.clean_value({"key": "note", "type": "text"}, "设备无法开机") == "设备无法开机"
    assert business_fields.clean_value({"key": "note", "type": "text"}, "没有") is None  # 否定值不采信

    assert business_fields.clean_value({"key": "name", "type": "string"}, "我") is None  # 姓名黑名单
    assert business_fields.clean_value({"key": "name", "type": "string"}, "张三") == "张三"
