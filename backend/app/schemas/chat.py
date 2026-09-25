"""对话相关 Schema"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# 业务上下文硬上限（与 services/context.py 保持一致）
_MAX_CONTEXT_KEYS = 20
_MAX_CONTEXT_KEY_LEN = 50
_MAX_CONTEXT_VALUE_LEN = 500


class ChatMessageRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    visitor_id: str | None = None
    # 嵌入方可指定助手与业务上下文（均可空）
    assistant_id: str | None = None
    context: dict[str, Any] | None = None

    @field_validator("context")
    @classmethod
    def _check_context(cls, v):
        """入口粗校验：扁平对象、键数量受限、键为字符串、值为标量（精清洗在服务层）"""
        if v is None:
            return None
        if not isinstance(v, dict) or len(v) > _MAX_CONTEXT_KEYS:
            raise ValueError("context 必须是不超过 20 个键的 JSON 对象")
        for key, value in v.items():
            if not isinstance(key, str) or not key or len(key) > _MAX_CONTEXT_KEY_LEN:
                raise ValueError("context 的键必须是 1-50 字符的字符串")
            if isinstance(value, bool):
                continue
            if not isinstance(value, (str, int, float)) or value is None:
                raise ValueError("context 的值只能是字符串/数字/布尔等标量")
            if isinstance(value, str) and len(value) > _MAX_CONTEXT_VALUE_LEN:
                raise ValueError("context 单个值长度不能超过 500 字符")
        return v


class ChatMessageResponse(BaseModel):
    conversation_id: str | None = None
    reply: str
    sources: list[dict] = []
    assistant_id: str = "default"
    # 通用业务数据采集结果（data_type: lead/ticket/requirement/appointment/custom）
    data_captured: bool = False
    data_type: str | None = None


class CreateConversationRequest(BaseModel):
    website_id: str | None = None
    visitor_id: str | None = None
    assistant_id: str | None = None
    context: dict[str, Any] | None = None


class CreateConversationResponse(BaseModel):
    conversation_id: str
    assistant_id: str = "default"


class ConversationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    website_id: str | None = None
    visitor_id: str | None = None
    assistant_id: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationOut]
    total: int


class MessageOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    role: str
    content: str
    sources: list[dict] | None = None
    created_at: datetime | None = None


class MessageListResponse(BaseModel):
    messages: list[MessageOut]


class StatsResponse(BaseModel):
    today_conversations: int = 0
    today_collected: int = 0
    total_conversations: int = 0
    total_collected: int = 0
    total_messages: int = 0
    total_documents: int = 0
