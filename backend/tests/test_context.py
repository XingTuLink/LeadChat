"""Web Context 清洗服务测试（任务书第 11-13 节安全最小实现）"""
from app.services import context as ctx


def test_sanitize_whitelist_filters_unknown_keys():
    cfg = {"allowed_fields": ["page", "order_id"], "max_keys": 20}
    out = ctx.sanitize_context(
        {"page": "/ticket", "order_id": "O-1", "secret": "x", 1: "numeric-key"}, cfg
    )
    assert out == {"page": "/ticket", "order_id": "O-1"}


def test_sanitize_empty_whitelist_allows_all_scalars():
    out = ctx.sanitize_context({"a": "1", "b": 2, "c": True}, {"allowed_fields": []})
    assert out == {"a": "1", "b": "2", "c": "True"}


def test_sanitize_rejects_nested_and_none():
    out = ctx.sanitize_context(
        {"obj": {"nested": 1}, "arr": [1, 2], "nil": None, "ok": "yes"},
        {"allowed_fields": []},
    )
    assert out == {"ok": "yes"}


def test_sanitize_non_dict_input():
    assert ctx.sanitize_context(None) == {}
    assert ctx.sanitize_context([1, 2]) == {}
    assert ctx.sanitize_context("str") == {}


def test_sanitize_limits_and_lengths():
    # 键数上限：只保留前 20 个
    big = {f"k{i}": str(i) for i in range(25)}
    out = ctx.sanitize_context(big, {"allowed_fields": [], "max_keys": 20})
    assert len(out) == 20

    # 超长键 / 超长值丢弃
    out2 = ctx.sanitize_context(
        {"x" * 51: "v", "long": "v" * 501, "fine": "v" * 500},
        {"allowed_fields": []},
    )
    assert "fine" in out2 and len(out2["fine"]) == 500
    assert "long" not in out2 and "x" * 51 not in out2

    # 空字符串值丢弃
    assert ctx.sanitize_context({"blank": "   "}, {"allowed_fields": []}) == {}


def test_inject_context_block():
    prompt = "BASE PROMPT"
    injected = ctx.inject_context(prompt, {"order_id": "O-9"})
    assert "BASE PROMPT" in injected
    assert "【业务上下文】" in injected
    assert "order_id: O-9" in injected
    # 空上下文不改写
    assert ctx.inject_context(prompt, None) == prompt
    assert ctx.inject_context(prompt, {}) == prompt
