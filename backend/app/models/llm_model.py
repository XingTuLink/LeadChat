"""LLM 对话模型配置：全部在后台「模型管理」中维护，支持多模型在线切换

同一时刻仅有一条 is_active=True 的记录，作为全局对话模型生效。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LLMModel(Base):
    """可用对话模型（provider + model_name + 凭证 + 端点）"""

    __tablename__ = "llm_models"

    # 短 slug，便于 API 操作（自动生成 model-xxxxxxxx 或创建时指定）
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # openai / deepseek / qwen / glm / ollama / custom
    provider: Mapped[str] = mapped_column(String(32), default="openai")
    # 模型标识，如 deepseek-chat / gpt-4o-mini / qwen-plus
    model_name: Mapped[str] = mapped_column(String(100))
    # API 密钥；Ollama 等本地模型可空
    api_key: Mapped[str | None] = mapped_column(Text, default=None)
    # OpenAI 兼容端点；留空用各厂商默认端点
    api_base: Mapped[str | None] = mapped_column(String(255), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
