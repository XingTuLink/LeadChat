"""Business Context 服务（任务书第 11-13、27 节）

宿主 Web 系统通过 Embed API 上送 JSON 上下文（user_id / page / record_id …），
经安全清洗后注入 System Prompt，让 LeadChat 从「官网挂件」变为可嵌入任意
Web 系统（CRM / ERP / OA / 客户门户）的 AI Interaction Layer。

安全最小实现（任务书第 27 节）：
- 只接受扁平 JSON 对象，值必须是标量（str/int/float/bool），拒绝嵌套对象/数组；
- 键数量、键长度、值长度均有硬上限；
- Assistant 可配置 allowed_context_fields 白名单（空数组=不限制，仅做清洗）；
- 被丢弃的键不会进入 Prompt，也不会持久化。
"""
from typing import Any

MAX_CONTEXT_KEYS = 20
MAX_KEY_LEN = 50
MAX_VALUE_LEN = 500
_SCALAR = (str, int, float, bool)


def sanitize_context(context: Any, context_config: dict | None = None) -> dict[str, str]:
    """清洗宿主上送的业务上下文。返回可安全注入 Prompt / 持久化的扁平字符串字典"""
    if not isinstance(context, dict):
        return {}

    cfg = context_config or {}
    allowed = cfg.get("allowed_fields") or []
    allowed_set = {str(k) for k in allowed} if isinstance(allowed, list) else set()
    max_keys = int(cfg.get("max_keys") or MAX_CONTEXT_KEYS)
    max_keys = min(max(max_keys, 0), MAX_CONTEXT_KEYS)

    result: dict[str, str] = {}
    for key, value in context.items():
        if len(result) >= max_keys:
            break
        key = str(key)
        if not key or len(key) > MAX_KEY_LEN:
            continue
        if allowed_set and key not in allowed_set:
            continue
        # None 视为未提供；嵌套对象/数组拒绝（防止把宿主内部数据整包灌给 LLM）
        if value is None or not isinstance(value, _SCALAR):
            continue
        text = str(value).strip()
        if not text or len(text) > MAX_VALUE_LEN:
            continue
        result[key] = text
    return result


def render_context_block(context: dict[str, str]) -> str:
    """渲染为注入系统提示词的上下文段落"""
    if not context:
        return ""
    lines = "\n".join(f"- {k}: {v}" for k, v in context.items())
    return (
        "\n\n【业务上下文】以下信息由宿主业务系统通过嵌入接口提供，"
        "代表用户当前所在的页面/记录/身份，仅用于理解用户场景，不要主动向用户念出这些技术字段：\n"
        + lines
    )


def inject_context(system_prompt: str, context: dict[str, str] | None) -> str:
    """把业务上下文插入系统提示词（位于 Instructions 之后、RAG 资料之前）"""
    block = render_context_block(context or {})
    if not block:
        return system_prompt
    return system_prompt + block
