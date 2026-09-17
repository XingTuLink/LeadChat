"""Assistant 核心领域模型

- Assistant：嵌入某个 Web 系统的 AI 助手（网站助手 / 客服 / 内部 Copilot…）
- BusinessField：Assistant 需要理解或采集的通用结构化字段（姓名/电话/订单号/预算…一律平等）
- CollectedData：对话过程中采集到的结构化业务数据，按 data_type 解释为
  线索(lead) / 工单(ticket) / 需求(requirement) / 预约(appointment) / 自定义(custom)。
  Lead 只是其中一种数据类型，不是独立领域对象。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Assistant(Base):
    """助手：Instructions + Model + Knowledge + Business Fields + Context + UI 的聚合"""

    __tablename__ = "assistants"

    # 短 slug，便于直接写进嵌入代码（如 default / support）
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    # 场景模板：general / support / internal / requirement / sales
    scenario: Mapped[str] = mapped_column(String(32), default="general")

    # Instructions（default 助手留空时继承系统设置中的全局 system_prompt）
    system_prompt: Mapped[str | None] = mapped_column(Text, default=None)

    # 预留：模型覆盖配置（本期实际模型仍走全局 .env），如 {"provider": "...", "model": "..."}
    model_config: Mapped[str | None] = mapped_column(Text, default=None)
    # 预留：知识源范围，本期 {"scope": "global"} 使用全局知识库
    knowledge_config: Mapped[str | None] = mapped_column(Text, default=None)
    # 业务上下文安全配置：{"allowed_fields": ["page", "record_id"], "max_keys": 20}
    # allowed_fields 为空数组表示不限制（仅做类型/长度清洗）
    context_config: Mapped[str | None] = mapped_column(Text, default=None)
    # 采集配置：{"mode": "ask|collect", "data_type": "lead|ticket|requirement|appointment|custom",
    #          "intent_hint": "...", "guide_message": "..."}
    collect_config: Mapped[str | None] = mapped_column(Text, default=None)
    # 外观配置：{"theme","icon","title","welcome_message","popup_message","auto_popup_delay","position"}
    # 留空字段回退全局挂件配置
    ui_config: Mapped[str | None] = mapped_column(Text, default=None)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active / disabled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class BusinessField(Base):
    """业务字段定义：AI 在当前业务场景中需要理解或采集的结构化信息"""

    __tablename__ = "business_fields"
    __table_args__ = (UniqueConstraint("assistant_id", "field_key", name="uq_business_field_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assistant_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("assistants.id", ondelete="CASCADE"), index=True
    )
    field_key: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(100))
    # string / text / number / enum / phone / email
    field_type: Mapped[str] = mapped_column(String(20), default="string")
    # enum 可选项（JSON 数组字符串），其余类型为 None
    options: Mapped[str | None] = mapped_column(Text, default=None)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CollectedData(Base):
    """采集数据：对话中获得的通用结构化业务信息（Lead / Ticket / Requirement… 的统一底座）"""

    __tablename__ = "collected_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id"), default=None, index=True
    )
    assistant_id: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    # 业务解释类型：lead / ticket / requirement / appointment / custom
    data_type: Mapped[str] = mapped_column(String(32), default="custom", index=True)
    # 全部字段值平铺：{field_key: value}
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new / processed / closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
