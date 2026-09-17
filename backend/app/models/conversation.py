"""对话模型：User ↔ Conversation ↔ Assistant ↔ Messages

对话本身不绑定任何业务类型；结构化业务产物统一进入 collected_data。
"""
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    website_id: Mapped[str | None] = mapped_column(String(64), default=None)
    visitor_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    # 对话中由采集器抽取、尚未收齐的字段草稿（JSON 扁平结构：{field_key: value}）
    draft_json: Mapped[str | None] = mapped_column(Text, default=None)
    # 对话归属的助手（旧对话为空，运行时等价于 default）
    assistant_id: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    # 宿主 Web 系统通过 Embed API 上送的业务上下文（JSON，已经过白名单清洗）
    context_json: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
