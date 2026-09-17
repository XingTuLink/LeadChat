"""Collected Data（通用采集数据）相关 Schema"""
import json
from datetime import datetime

from pydantic import BaseModel, field_validator


class CollectedDataOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    conversation_id: str | None = None
    assistant_id: str | None = None
    data_type: str
    payload: dict
    status: str
    created_at: datetime | None = None

    @field_validator("payload", mode="before")
    @classmethod
    def _parse_payload(cls, v):
        if isinstance(v, str):
            try:
                data = json.loads(v)
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
        return v or {}


class CollectedDataListResponse(BaseModel):
    items: list[CollectedDataOut]
    total: int


class CollectedDataUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        allowed = {"new", "processed", "closed"}
        if v not in allowed:
            raise ValueError(f"status 必须是 {'/'.join(allowed)} 之一")
        return v
