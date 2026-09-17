"""Business Fields 服务：通用结构化字段定义的读取与按类型校验/清洗

所有字段一律平等——姓名、电话、订单号、预算没有领域高下之分；
字段如何使用完全由 Assistant 配置决定（可用于线索、工单、需求、预约、报名…）。
支持类型：string / text / number / enum / phone / email。
"""
import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import BusinessField
from app.services import assistant_store

VALID_TYPES = {"string", "text", "number", "enum", "phone", "email"}

_PHONE_RE = re.compile(r"1[3-9]\d{9}|\+?\d[\d\s-]{6,16}\d")
_EMAIL_RE = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
# name 是极常见的字段 key，对其做通用的称呼质量校验（并非销售专属）
_NAME_BLACKLIST = {
    "我", "你", "他", "她", "您", "我们", "你们", "他们", "自己",
    "客户", "用户", "访客", "客服", "顾问", "经理", "老板",
    "先生", "女士", "老师", "师傅", "帅哥", "美女", "朋友",
}
_NEGATIVE_VALUES = {
    "无", "没有", "没", "未提供", "未知", "暂无", "不知道", "没说", "未告知",
    "未填写", "n/a", "na", "null", "none", "nil", "/", "-",
}


def normalize_field(raw: dict) -> dict:
    """归一化字段配置（来源可能是 business_fields 行或全局 KV business_fields）"""
    key = str(raw.get("key") or "").strip()
    field_type = str(raw.get("type") or raw.get("field_type") or "string").strip().lower()
    if field_type not in VALID_TYPES:
        field_type = "string"
    options = raw.get("options")
    if not isinstance(options, list):
        options = []
    return {
        "key": key,
        "label": str(raw.get("label") or key).strip() or key,
        "type": field_type,
        "options": [str(o) for o in options if str(o).strip()],
        "required": bool(raw.get("required")),
        "sort_order": int(raw.get("sort_order", 0) or 0),
    }


def global_fields(global_cfg: dict) -> list[dict]:
    """解析全局业务字段配置（默认助手的字段回退来源）"""
    fields: list[dict] = []
    seen: set[str] = set()
    for f in global_cfg.get("business_fields") or []:
        key = str(f.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        fields.append(normalize_field({
            "key": key,
            "label": f.get("label"),
            "type": f.get("type"),
            "options": f.get("options"),
            "required": bool(f.get("required")),
        }))
    return fields


async def get_runtime_fields(
    session: AsyncSession, assistant, global_cfg: dict
) -> list[dict]:
    """运行时字段列表：Assistant 自定义字段优先；默认助手留空则回退全局配置"""
    if assistant is None:
        return global_fields(global_cfg)

    rows = await assistant_store.list_fields(session, assistant.id)
    if rows:
        return [
            normalize_field({
                "key": r.field_key, "label": r.label, "type": r.field_type,
                "options": json.loads(r.options) if r.options else [],
                "required": r.required, "sort_order": r.sort_order,
            })
            for r in rows
        ]
    if assistant.id == assistant_store.DEFAULT_ASSISTANT_ID:
        return global_fields(global_cfg)
    return []


# ---------------------------------------------------------------- 按类型清洗

def clean_name(value) -> str | None:
    name = str(value or "").strip().strip("。，,.!！?？\"'“”‘’")
    if not name or len(name) < 2 or len(name) > 30:
        return None
    if name in _NAME_BLACKLIST:
        return None
    if re.search(r"[，。！？?,.!；;：:]", name):
        return None
    return name[:100] or None


def clean_phone(value) -> str | None:
    phone = str(value or "").strip()
    if not phone:
        return None
    match = _PHONE_RE.search(phone.replace(" ", ""))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group())
    if len(digits) < 7 or len(digits) > 15:
        return None
    return match.group().strip()


def clean_email(value) -> str | None:
    email = str(value or "").strip()
    match = _EMAIL_RE.search(email)
    return match.group() if match else None


def clean_number(value) -> str | None:
    text = str(value or "").strip()
    match = _NUMBER_RE.search(text.replace(",", ""))
    return match.group() if match else None


def clean_enum(value, options: list[str]) -> str | None:
    text = str(value or "").strip().strip("。，,.!！?？\"'“”‘’")
    if not text:
        return None
    for opt in options:
        if text == opt or opt in text:
            return opt
    return None


def clean_generic(value) -> str | None:
    v = str(value or "").strip().strip("。，,.!！?？\"'“”‘’")
    if not v:
        return None
    if v.lower() in _NEGATIVE_VALUES:
        return None
    return v[:200] or None


def clean_value(field: dict, value) -> str | None:
    """按字段定义清洗抽取值；不合格一律返回 None（只采信明确信息）"""
    if value is None:
        return None
    key = field["key"]
    if key == "name":
        return clean_name(value)
    if field["type"] == "phone":
        return clean_phone(value)
    if field["type"] == "email":
        return clean_email(value)
    if field["type"] == "number":
        return clean_number(value)
    if field["type"] == "enum":
        return clean_enum(value, field.get("options") or [])
    return clean_generic(value)
