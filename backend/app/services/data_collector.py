"""通用业务数据采集器（COLLECT 模式）

与具体业务解耦：采集哪些字段、产出何种数据类型（lead / ticket / requirement /
appointment / custom）全部由 Assistant 的 collect_config + business_fields 决定。

状态机：idle → collecting → captured（同一会话幂等，已产出数据后为 done）

- 采集草稿以扁平 JSON {field_key: value} 存放在 conversations.draft_json；
- 必填字段全部收齐后，一次性写入 collected_data，作为唯一的结构化产物。
"""
import json
import logging

from sqlalchemy import select

from app.models.assistant import CollectedData
from app.services import business_fields, llm

logger = logging.getLogger("leadchat.data_collector")

MODE_COLLECT = "collect"

_EXTRACT_PROMPT = """你是信息抽取助手。请从【用户最新消息】及对话上下文中，抽取用户【主动、明确】提供的信息。

规则：
1. 只抽取用户明确说出的内容，严禁推测、脑补或使用历史中的假设性表述；
2. 无法确认的字段输出 null，不要输出空字符串；
3. 严格输出 JSON，不要输出任何解释或 Markdown。

目标字段：
{fields_desc}
{intent_line}
输出格式：{{"has_intent": true/false, "fields": {{"field_key": "用户原始表述或 null"}}}}"""


def _idle() -> dict:
    return {"stage": "idle"}


def _done(data_type: str) -> dict:
    return {"stage": "done", "data_type": data_type}


def load_draft(conv) -> dict:
    """读取对话上的采集草稿（扁平结构）"""
    if not conv.draft_json:
        return {}
    try:
        data = json.loads(conv.draft_json)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def save_draft(conv, draft: dict) -> None:
    conv.draft_json = json.dumps(draft, ensure_ascii=False) if draft else None


async def _existing_data(session, conv) -> CollectedData | None:
    return (
        await session.execute(
            select(CollectedData).where(CollectedData.conversation_id == conv.id).limit(1)
        )
    ).scalars().first()


async def analyze_conversation(
    user_message: str, history: list[dict], field_defs: list[dict], intent_hint: str = ""
) -> tuple[bool, dict]:
    """一次 LLM 调用同时完成「是否在提供信息」判断与字段抽取。

    返回 (has_intent, {field_key: 原始值})；LLM 不可用时降级为字段格式正则抽取。
    """
    fields_desc = "\n".join(
        f'- {f["key"]}（{f["label"]}，{f["type"]}）' + ("【必填】" if f["required"] else "")
        for f in field_defs
    )
    intent_line = f"判断重点：{intent_hint}\n" if intent_hint else ""
    messages = [
        {"role": "system", "content": _EXTRACT_PROMPT.format(
            fields_desc=fields_desc, intent_line=intent_line
        )},
        *history[-8:],
        {"role": "user", "content": user_message},
    ]
    try:
        raw = await llm.chat_completion(messages, temperature=0.0)
        parsed = _parse_json_object(raw)
        fields_raw = parsed.get("fields") if isinstance(parsed, dict) else None
        if not isinstance(fields_raw, dict):
            fields_raw = {}
        extracted = {
            f["key"]: business_fields.clean_value(f, fields_raw.get(f["key"]))
            for f in field_defs
        }
        extracted = {k: v for k, v in extracted.items() if v}
        has_intent = bool(parsed.get("has_intent")) or bool(extracted)
        return has_intent, extracted
    except Exception as e:  # noqa: BLE001  抽取失败不应影响主对话
        logger.warning("信息抽取失败，降级正则: %s", e)
        return _fallback_extract(user_message, field_defs)


def _parse_json_object(raw: str) -> dict:
    """从模型输出中提取 JSON 对象"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("模型输出中未找到 JSON 对象")
    return json.loads(text[start:end + 1])


def _fallback_extract(user_message: str, field_defs: list[dict]) -> tuple[bool, dict]:
    """无 LLM 时的降级：仅按字段类型抽取电话/邮箱等强格式信息"""
    extracted: dict = {}
    for f in field_defs:
        value = business_fields.clean_value(f, user_message)
        if value:
            extracted[f["key"]] = value
    return bool(extracted), extracted


async def run_collection(session, conv, user_message, history, cfg, assistant) -> dict:
    """执行一轮采集，返回采集状态（见模块状态机说明）"""
    mode = cfg.get("collect_mode")
    field_defs = cfg.get("business_fields") or []
    data_type = cfg.get("collect_data_type") or "custom"

    if mode != MODE_COLLECT or not field_defs:
        return _idle()

    existing = await _existing_data(session, conv)
    if existing:
        return _done(existing.data_type)

    has_intent, extracted = await analyze_conversation(
        user_message, history, field_defs, cfg.get("collect_intent_hint", "")
    )
    if not has_intent and not extracted:
        return _idle()

    draft = load_draft(conv)
    draft.update(extracted)

    required = [f for f in field_defs if f["required"]]
    missing = [f for f in required if not draft.get(f["key"])]

    if required and not missing:
        record = CollectedData(
            conversation_id=conv.id,
            assistant_id=assistant.id if assistant else None,
            data_type=data_type,
            payload=json.dumps(draft, ensure_ascii=False),
            status="new",
        )
        session.add(record)
        await session.flush()
        save_draft(conv, {})
        return {
            "stage": "captured",
            "data_type": data_type,
            "collected_data_id": record.id,
            "draft": dict(draft),
            "missing": [],
        }

    save_draft(conv, draft)
    return {
        "stage": "collecting",
        "data_type": data_type,
        "draft": dict(draft),
        "missing": [f["key"] for f in missing],
        "missing_labels": [f["label"] for f in missing],
    }


def build_collection_instruction(collection: dict, cfg: dict) -> str:
    """根据采集状态向主回复 Prompt 追加行为指令（不产生面向用户的固定话术）"""
    stage = collection.get("stage")
    if stage == "collecting":
        labels = collection.get("missing_labels") or []
        next_label = labels[0] if labels else "必要信息"
        guide = cfg.get("collect_guide_message") or ""
        return (
            f"\n\n【信息收集】你正在协助用户记录信息，目前还缺少：{next_label}。"
            "请用自然、简短的对话方式只追问这一项，不要像填表、不要罗列全部问题、"
            "不要重复追问用户已经提供过的信息。"
            + (f"整体语气参考：{guide}" if guide else "")
        )
    if stage == "captured":
        return "\n\n【信息收集】用户所需提供的信息已经记录完整，请用一两句话自然地确认并说明会跟进处理。"
    return ""
