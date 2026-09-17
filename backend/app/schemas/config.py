"""系统配置相关 Schema"""
from typing import Any

from pydantic import BaseModel


class ConfigUpdateRequest(BaseModel):
    key: str
    value: Any


class ConfigResponse(BaseModel):
    config: dict


class WidgetConfigResponse(BaseModel):
    company_name: str = "LeadChat"
    welcome_message: str = "你好，我是这个系统的 AI 助手，可以帮你查询信息、回答问题或协助完成相关操作。"
    popup_message: str = "您好，请问有什么可以帮您吗？"
    auto_popup_delay: float = 3
    widget_theme: str = "#4F46E5"
    widget_position: str = "right"
    widget_icon: str = "chat"
    # 通用业务字段（ASK 模式下仅为字段定义，不触发采集）
    business_fields: list[dict] = []
    footer_enabled: bool = True
    # 实际生效的助手 ID（挂件随消息回传，保证配置与采集规则一致）
    assistant_id: str = "default"
    # 交互模式：ask（只问答）/ collect（采集业务信息）
    collect_mode: str = "ask"
