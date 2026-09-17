"""Assistant 存储服务：场景模板、CRUD、默认 Assistant 播种与运行时配置解析

设计要点：
- 启动时幂等播种 id="default" 的默认 Assistant；默认助手是一个**通用问答助手**
  （general / ask），话术与外观留空 → 继承系统设置全局值，不含任何业务预设；
- 运行时配置 runtime_config() 在全局 KV 配置 dict 上叠加 Assistant 个性化配置，
  下游（chat_engine / data_collector）拿到统一的 cfg dict；
- 场景模板只是 Default Prompt + Default Fields + Default Context + Default UI，
  不是不同代码；销售线索（sales）只是模板之一，排在最后。
"""
import json
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant, BusinessField

DEFAULT_ASSISTANT_ID = "default"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

# Interaction modes：ASK（问答）/ COLLECT（采集业务字段）
MODE_ASK = "ask"
MODE_COLLECT = "collect"

DEFAULT_CONTEXT_CONFIG = {"allowed_fields": [], "max_keys": 20}
DEFAULT_COLLECT_CONFIG = {"mode": MODE_ASK, "data_type": "custom", "intent_hint": ""}


# ---------------------------------------------------------------- 场景模板
# 顺序即后台展示顺序：通用 → 客服 → 内部 → 需求 → 销售线索（Lead Generation 置末）

SCENARIO_TEMPLATES: dict[str, dict[str, Any]] = {
    "general": {
        "label": "网站助手",
        "description": "通用 Website Assistant：基于知识库回答问题，不主动采集信息",
        "system_prompt": (
            "你是{company_name}的AI助手，嵌入在用户正在使用的 Web 系统中。\n\n"
            "你的职责：\n"
            "1. 专业、友好地回答用户关于{business_description}的问题\n"
            "2. 优先依据知识库资料作答，协助用户查询信息、了解产品与服务\n\n"
            "回答规则：\n"
            "- 优先基于【参考资料】回答，不要编造信息\n"
            "- 如果参考资料中没有相关信息，诚实告知用户\n"
            "- 回答简洁、有条理，每次不超过200字\n"
            "- 使用与用户相同的语言回答"
        ),
        "collect": {"mode": MODE_ASK, "data_type": "custom", "intent_hint": ""},
        "fields": [],
        "context": {"allowed_fields": [], "max_keys": 20},
        "ui": {},
    },
    "support": {
        "label": "客服助手",
        "description": "Customer Service：解答使用问题，收集订单与故障信息生成工单",
        "system_prompt": (
            "你是{company_name}的AI客服助手。\n\n"
            "你的职责：\n"
            "1. 依据{business_description}相关资料，专业地解答产品使用、故障排查与售后政策问题\n"
            "2. 需要核单或转人工处理时，自然地收集订单号、问题类型等信息\n"
            "3. 语气耐心、负责，不推卸责任\n\n"
            "回答规则：\n"
            "- 优先基于【参考资料】回答，不要编造信息\n"
            "- 涉及退款/赔偿等超出权限的承诺，引导转人工处理\n"
            "- 回答要简洁、有条理，步骤类问题分点说明\n"
            "- 使用与用户相同的语言回答"
        ),
        "collect": {"mode": MODE_COLLECT, "data_type": "ticket",
                    "intent_hint": "用户是否遇到产品/订单问题需要支持，或正在提供订单、产品信息"},
        "fields": [
            {"key": "order_id", "label": "订单号", "type": "string", "required": True},
            {"key": "issue_type", "label": "问题类型", "type": "enum",
             "options": ["使用咨询", "故障报修", "退换货", "账单问题"], "required": True},
            {"key": "phone", "label": "联系电话", "type": "phone", "required": False},
            {"key": "issue_detail", "label": "问题描述", "type": "text", "required": False},
        ],
        "context": {"allowed_fields": ["page", "user_id", "order_id", "product_model"], "max_keys": 20},
        "ui": {},
    },
    "internal": {
        "label": "内部 Copilot",
        "description": "Internal Copilot：员工查询业务知识、流程制度的问答伙伴",
        "system_prompt": (
            "你是{company_name}的内部 AI 助手。\n\n"
            "你的职责：\n"
            "1. 基于企业知识库回答员工关于业务流程、制度规范、产品信息的问题\n"
            "2. 结合宿主系统提供的业务上下文（如当前页面、记录 ID）给出针对性回答\n\n"
            "回答规则：\n"
            "- 优先基于【参考资料】回答，不要编造制度或流程\n"
            "- 回答简洁、有条理，涉及操作步骤时分点说明\n"
            "- 使用与用户相同的语言回答"
        ),
        "collect": {"mode": MODE_ASK, "data_type": "custom", "intent_hint": ""},
        "fields": [],
        "context": {"allowed_fields": [], "max_keys": 20},
        "ui": {},
    },
    "requirement": {
        "label": "需求收集助手",
        "description": "Requirement Collection：售前咨询/项目场景，在对话中结构化收集用户需求",
        "system_prompt": (
            "你是{company_name}的AI需求收集助手。\n\n"
            "你的职责：\n"
            "1. 基于{business_description}相关资料解答用户问题\n"
            "2. 在用户表达需求、问题或合作意向时，像顾问一样自然地了解具体诉求\n"
            "3. 语气专业、耐心，帮助用户理清需求\n\n"
            "回答规则：\n"
            "- 优先基于【参考资料】回答，不要编造信息\n"
            "- 每次只追问一个缺失的关键信息，不要像填表\n"
            "- 不要提及“表单”“填写”“系统”等字眼\n"
            "- 使用与用户相同的语言回答"
        ),
        "collect": {"mode": MODE_COLLECT, "data_type": "requirement",
                    "intent_hint": "用户是否正在描述具体需求、问题，或希望提交反馈/合作意向"},
        "fields": [
            {"key": "requirement", "label": "需求描述", "type": "text", "required": True},
            {"key": "name", "label": "姓名", "type": "string", "required": False},
            {"key": "phone", "label": "联系电话", "type": "phone", "required": False},
        ],
        "context": {"allowed_fields": [], "max_keys": 20},
        "ui": {},
    },
    "sales": {
        "label": "销售线索助手",
        "description": "Lead Generation（众多应用场景之一）：官网售前咨询，在对话中收集客户联系方式",
        "system_prompt": (
            "你是{company_name}的AI销售助手。\n\n"
            "你的职责：\n"
            "1. 热情、专业地回答用户关于{business_description}的问题\n"
            "2. 当用户表达合作意向或询问价格时，自然地引导对方留下联系方式\n"
            "3. 始终保持友好、有帮助的态度\n\n"
            "回答规则：\n"
            "- 优先基于【参考资料】回答，不要编造信息\n"
            "- 如果参考资料中没有相关信息，诚实告知用户\n"
            "- 回答要简洁、有条理，每次不超过200字\n"
            "- 使用与用户相同的语言回答"
        ),
        "collect": {"mode": MODE_COLLECT, "data_type": "lead",
                    "intent_hint": "用户是否表达了合作/购买/报价意向，或愿意留下联系方式"},
        "fields": [
            {"key": "name", "label": "姓名", "type": "string", "required": True},
            {"key": "phone", "label": "电话", "type": "phone", "required": True},
            {"key": "email", "label": "邮箱", "type": "email", "required": False},
            {"key": "requirement", "label": "需求描述", "type": "text", "required": False},
        ],
        "context": {"allowed_fields": [], "max_keys": 20},
        "ui": {},
    },
}


def _dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return json.loads(json.dumps(default))
    try:
        data = json.loads(value)
        return data if data is not None else json.loads(json.dumps(default))
    except (json.JSONDecodeError, TypeError):
        return json.loads(json.dumps(default))


def template_meta() -> list[dict]:
    """模板列表（供后台选择与新建表单预填，仅管理端可见，含完整默认配置）"""
    return [
        {
            "key": k,
            "label": v["label"],
            "description": v["description"],
            "system_prompt": v["system_prompt"],
            "collect": v["collect"],
            "fields": v["fields"],
            "context": v["context"],
            "ui": v.get("ui", {}),
        }
        for k, v in SCENARIO_TEMPLATES.items()
    ]


# ---------------------------------------------------------------- 播种

async def ensure_default_assistant(session: AsyncSession) -> Assistant:
    """幂等创建默认 Assistant：通用问答助手，话术/外观继承系统设置，不主动采集。"""
    existing = await session.get(Assistant, DEFAULT_ASSISTANT_ID)
    if existing:
        return existing
    general = SCENARIO_TEMPLATES["general"]
    assistant = Assistant(
        id=DEFAULT_ASSISTANT_ID,
        name="默认助手",
        description="系统默认的通用 AI 助手；话术、外观与字段继承「系统设置」",
        scenario="general",
        system_prompt=None,  # 继承全局 system_prompt
        model_config=None,
        knowledge_config=_dumps({"scope": "global"}),
        context_config=_dumps(DEFAULT_CONTEXT_CONFIG),
        collect_config=_dumps(general["collect"]),  # ask / custom：默认不采集
        ui_config=None,  # 继承全局挂件外观
        is_default=True,
        status="active",
    )
    # 默认助手不创建 business_fields 行：运行时回退到全局 business_fields
    session.add(assistant)
    await session.commit()
    return assistant


# ---------------------------------------------------------------- 查询

async def get_default(session: AsyncSession) -> Assistant | None:
    row = (
        await session.execute(select(Assistant).where(Assistant.is_default.is_(True)).limit(1))
    ).scalars().first()
    return row or await session.get(Assistant, DEFAULT_ASSISTANT_ID)


async def resolve_assistant(session: AsyncSession, assistant_id: str | None) -> Assistant:
    """按嵌入代码指定的 id 解析助手；缺失/停用/不存在时回退默认助手"""
    if assistant_id:
        row = await session.get(Assistant, assistant_id)
        if row and row.status == "active":
            return row
    return await ensure_default_assistant(session)


async def list_assistants(session: AsyncSession) -> list[Assistant]:
    return list(
        (await session.execute(select(Assistant).order_by(Assistant.is_default.desc(), Assistant.created_at.asc())))
        .scalars().all()
    )


async def list_fields(session: AsyncSession, assistant_id: str) -> list[BusinessField]:
    return list(
        (
            await session.execute(
                select(BusinessField)
                .where(BusinessField.assistant_id == assistant_id)
                .order_by(BusinessField.sort_order.asc(), BusinessField.id.asc())
            )
        )
        .scalars().all()
    )


def field_to_dict(row: BusinessField) -> dict:
    return {
        "key": row.field_key,
        "label": row.label,
        "type": row.field_type,
        "options": _loads(row.options, []),
        "required": bool(row.required),
        "sort_order": row.sort_order,
    }


async def assistant_to_dict(session: AsyncSession, assistant: Assistant) -> dict:
    fields = [field_to_dict(r) for r in await list_fields(session, assistant.id)]
    return {
        "id": assistant.id,
        "name": assistant.name,
        "description": assistant.description or "",
        "scenario": assistant.scenario,
        "system_prompt": assistant.system_prompt or "",
        "model_config": _loads(assistant.model_config, {}),
        "knowledge_config": _loads(assistant.knowledge_config, {"scope": "global"}),
        "context_config": _loads(assistant.context_config, DEFAULT_CONTEXT_CONFIG),
        "collect_config": _loads(assistant.collect_config, DEFAULT_COLLECT_CONFIG),
        "ui_config": _loads(assistant.ui_config, {}),
        "business_fields": fields,
        "is_default": bool(assistant.is_default),
        "status": assistant.status,
        "created_at": assistant.created_at.isoformat() if assistant.created_at else None,
        "updated_at": assistant.updated_at.isoformat() if assistant.updated_at else None,
    }


# ---------------------------------------------------------------- 运行时配置

def get_collect_config(assistant: Assistant | None) -> dict:
    cfg = _loads(assistant.collect_config if assistant else None, DEFAULT_COLLECT_CONFIG)
    cfg.setdefault("mode", MODE_ASK)
    cfg.setdefault("data_type", "custom")
    return cfg


def get_context_config(assistant: Assistant | None) -> dict:
    if assistant is None:
        return dict(DEFAULT_CONTEXT_CONFIG)
    return _loads(assistant.context_config, DEFAULT_CONTEXT_CONFIG)


def get_ui_config(assistant: Assistant | None) -> dict:
    if assistant is None:
        return {}
    return _loads(assistant.ui_config, {})


async def runtime_config(session: AsyncSession, assistant: Assistant, global_cfg: dict) -> dict:
    """在全局 KV 配置上叠加 Assistant 个性化配置，输出下游统一使用的 cfg dict。

    - 默认助手留空项一律继承全局（系统设置页面继续对默认助手生效）；
    - 其他助手未配置的外观项也回退全局。
    """
    cfg = json.loads(json.dumps(global_cfg, ensure_ascii=False))

    # 系统提示词
    if assistant.system_prompt and assistant.system_prompt.strip():
        cfg["system_prompt"] = assistant.system_prompt

    # 业务字段（延迟导入避免循环依赖）
    from app.services import business_fields

    cfg["business_fields"] = await business_fields.get_runtime_fields(session, assistant, global_cfg)

    # 采集配置
    collect = get_collect_config(assistant)
    cfg["collect_mode"] = collect.get("mode", MODE_ASK)
    cfg["collect_data_type"] = collect.get("data_type", "custom")
    cfg["collect_intent_hint"] = collect.get("intent_hint", "")
    if collect.get("guide_message"):
        cfg["collect_guide_message"] = collect["guide_message"]

    cfg["assistant_id"] = assistant.id
    cfg["assistant_name"] = assistant.name
    return cfg


# ---------------------------------------------------------------- 写入

def validate_id(assistant_id: str) -> str:
    assistant_id = (assistant_id or "").strip().lower()
    if not ID_PATTERN.match(assistant_id):
        raise ValueError("助手 ID 只能包含小写字母、数字、中划线、下划线（32 字符内），且以字母或数字开头")
    return assistant_id


async def apply_fields(session: AsyncSession, assistant_id: str, fields: list[dict]) -> None:
    """用入参整体替换某助手的业务字段"""
    old_rows = await list_fields(session, assistant_id)
    for row in old_rows:
        await session.delete(row)
    await session.flush()

    seen: set[str] = set()
    for index, f in enumerate(fields):
        key = str(f.get("key") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        field_type = str(f.get("type") or "string").strip().lower()
        if field_type not in ("string", "text", "number", "enum", "phone", "email"):
            field_type = "string"
        options = f.get("options") if field_type == "enum" else None
        if not isinstance(options, list):
            options = []
        session.add(BusinessField(
            assistant_id=assistant_id,
            field_key=key[:50],
            label=str(f.get("label") or key).strip()[:100] or key,
            field_type=field_type,
            options=_dumps([str(o) for o in options if str(o).strip()][:50]) if options else None,
            required=bool(f.get("required")),
            sort_order=int(f.get("sort_order", index)),
        ))


async def create_assistant(session: AsyncSession, data: dict) -> Assistant:
    assistant_id = validate_id(data.get("id") or f"assistant-{uuid.uuid4().hex[:8]}")
    if await session.get(Assistant, assistant_id):
        raise ValueError(f"助手 ID 已存在：{assistant_id}")

    scenario = data.get("scenario") or "general"
    template = SCENARIO_TEMPLATES.get(scenario) or SCENARIO_TEMPLATES["general"]
    name = (data.get("name") or template["label"]).strip()[:100]
    system_prompt = data.get("system_prompt")
    if system_prompt is None or str(system_prompt).strip() == "":
        system_prompt = template["system_prompt"]
    collect = data.get("collect_config") or template["collect"]
    context_cfg = data.get("context_config") or template["context"]
    ui_cfg = data.get("ui_config") or template.get("ui") or {}
    fields = data.get("business_fields")
    if fields is None:
        fields = template["fields"]

    assistant = Assistant(
        id=assistant_id,
        name=name,
        description=(data.get("description") or template["description"]) or None,
        scenario=scenario,
        system_prompt=system_prompt,
        model_config=_dumps(data.get("model_config") or {}),
        knowledge_config=_dumps({"scope": "global"}),
        context_config=_dumps(context_cfg),
        collect_config=_dumps(collect),
        ui_config=_dumps(ui_cfg) if ui_cfg else None,
        is_default=False,
        status="active",
    )
    session.add(assistant)
    await session.flush()
    await apply_fields(session, assistant_id, fields)
    await session.commit()
    return assistant


async def update_assistant(session: AsyncSession, assistant_id: str, data: dict) -> Assistant:
    assistant = await session.get(Assistant, assistant_id)
    if not assistant:
        raise KeyError(assistant_id)

    if "name" in data and str(data["name"]).strip():
        assistant.name = str(data["name"]).strip()[:100]
    if "description" in data:
        assistant.description = (str(data["description"]).strip() or None)
    if "scenario" in data and data["scenario"]:
        assistant.scenario = str(data["scenario"])[:32]
    if "system_prompt" in data:
        assistant.system_prompt = str(data["system_prompt"]).strip() or None
    if "model_config" in data:
        assistant.model_config = _dumps(data["model_config"] or {})
    if "context_config" in data:
        assistant.context_config = _dumps(data["context_config"] or DEFAULT_CONTEXT_CONFIG)
    if "collect_config" in data:
        assistant.collect_config = _dumps(data["collect_config"] or DEFAULT_COLLECT_CONFIG)
    if "ui_config" in data:
        assistant.ui_config = _dumps(data["ui_config"]) if data["ui_config"] else None
    if "status" in data and data["status"] in ("active", "disabled"):
        assistant.status = data["status"]
    if "business_fields" in data:
        await apply_fields(session, assistant_id, data["business_fields"] or [])
    await session.commit()
    return assistant


async def set_default(session: AsyncSession, assistant_id: str) -> Assistant:
    assistant = await session.get(Assistant, assistant_id)
    if not assistant:
        raise KeyError(assistant_id)
    for row in await list_assistants(session):
        row.is_default = row.id == assistant_id
    assistant.status = "active"
    await session.commit()
    return assistant


async def delete_assistant(session: AsyncSession, assistant_id: str) -> None:
    if assistant_id == DEFAULT_ASSISTANT_ID:
        raise ValueError("默认助手不可删除")
    assistant = await session.get(Assistant, assistant_id)
    if not assistant:
        raise KeyError(assistant_id)
    for row in await list_fields(session, assistant_id):
        await session.delete(row)
    await session.delete(assistant)
    await session.commit()
