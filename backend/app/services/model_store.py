"""LLM 模型配置存储：CRUD、唯一激活、API Key 掩码

对话模型不再通过 .env 配置；启动后模型表为空，由管理员在后台添加并激活。
"""
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LLMModel

# 支持的厂商（顺序即后台展示顺序）
PROVIDERS: tuple[str, ...] = ("openai", "deepseek", "qwen", "glm", "ollama", "custom")

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

# 各厂商默认的 OpenAI 兼容端点（后台表单提示用）
PROVIDER_DEFAULT_BASES = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "ollama": "http://localhost:11434",
    "custom": "",
}


def provider_meta() -> list[dict[str, Any]]:
    """厂商列表（供后台表单渲染，单一数据源）"""
    return [
        {"key": k, "default_base": PROVIDER_DEFAULT_BASES.get(k, "")}
        for k in PROVIDERS
    ]


def mask_key(key: str | None) -> str:
    """API Key 掩码：保留前 4 后 4，中间打码；短 Key 全部打码"""
    k = (key or "").strip()
    if not k:
        return ""
    if len(k) <= 8:
        return "*" * len(k)
    return k[:4] + "*" * (len(k) - 8) + k[-4:]


def to_dict(row: LLMModel, *, masked: bool = True) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "model_name": row.model_name,
        "api_key": mask_key(row.api_key) if masked else (row.api_key or ""),
        "api_base": row.api_base or "",
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def validate_id(model_id: str) -> str:
    model_id = (model_id or "").strip().lower()
    if not ID_PATTERN.match(model_id):
        raise ValueError(
            "模型 ID 只能包含小写字母、数字、中划线、下划线（32 字符内），且以字母或数字开头"
        )
    return model_id


# ---------------------------------------------------------------- 查询

async def list_models(session: AsyncSession) -> list[LLMModel]:
    return list(
        (
            await session.execute(
                select(LLMModel).order_by(
                    LLMModel.is_active.desc(), LLMModel.created_at.asc()
                )
            )
        )
        .scalars()
        .all()
    )


async def get_active(session: AsyncSession) -> LLMModel | None:
    """返回当前激活模型；未激活任何模型时返回 None"""
    return (
        await session.execute(
            select(LLMModel).where(LLMModel.is_active.is_(True)).limit(1)
        )
    ).scalars().first()


# ---------------------------------------------------------------- 写入

def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """清洗入参：字符串去首尾空白，provider 归一化"""
    provider = str(data.get("provider") or "openai").strip().lower()
    if provider not in PROVIDERS:
        provider = "openai"

    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("模型名称不能为空")
    model_name = str(data.get("model_name") or "").strip()
    if not model_name:
        raise ValueError("模型标识不能为空")

    return {
        "name": name[:100],
        "provider": provider,
        "model_name": model_name[:100],
        "api_key": str(data.get("api_key") or "").strip()[:500],
        "api_base": str(data.get("api_base") or "").strip()[:255],
    }


async def create_model(session: AsyncSession, data: dict[str, Any]) -> LLMModel:
    model_id = data.get("id")
    model_id = validate_id(model_id) if model_id else f"model-{uuid.uuid4().hex[:8]}"
    if await session.get(LLMModel, model_id):
        raise ValueError(f"模型 ID 已存在：{model_id}")

    cleaned = _clean(data)
    want_active = bool(data.get("is_active"))
    if want_active:
        await session.execute(update(LLMModel).values(is_active=False))

    row = LLMModel(
        id=model_id,
        is_active=want_active,
        **cleaned,
    )
    session.add(row)
    await session.commit()
    return row


async def update_model(
    session: AsyncSession, model_id: str, data: dict[str, Any]
) -> LLMModel:
    row = await session.get(LLMModel, model_id)
    if not row:
        raise KeyError(model_id)

    # 仅更新传入字段（PUT 语义由 schema exclude_unset 保证）
    if "name" in data:
        name = str(data["name"] or "").strip()
        if name:
            row.name = name[:100]
    if "provider" in data:
        provider = str(data["provider"] or "openai").strip().lower()
        row.provider = provider if provider in PROVIDERS else "openai"
    if "model_name" in data:
        model_name = str(data["model_name"] or "").strip()
        if model_name:
            row.model_name = model_name[:100]
    if "api_base" in data:
        row.api_base = str(data["api_base"] or "").strip()[:255] or None
    if "api_key" in data:
        new_key = str(data["api_key"] or "").strip()
        # 空串 = 不修改；掩码回传（含 *）也视为不修改
        if new_key and "*" not in new_key:
            row.api_key = new_key[:500]

    if data.get("is_active"):
        await session.execute(update(LLMModel).values(is_active=False))
        row.is_active = True

    row.updated_at = datetime.now()
    await session.commit()
    return row


async def activate(session: AsyncSession, model_id: str) -> LLMModel:
    """激活指定模型，同时取消其他所有模型的激活态"""
    row = await session.get(LLMModel, model_id)
    if not row:
        raise KeyError(model_id)
    await session.execute(update(LLMModel).values(is_active=False))
    row.is_active = True
    row.updated_at = datetime.now()
    await session.commit()
    return row


async def delete_model(session: AsyncSession, model_id: str) -> None:
    row = await session.get(LLMModel, model_id)
    if not row:
        raise KeyError(model_id)
    await session.delete(row)
    await session.commit()
