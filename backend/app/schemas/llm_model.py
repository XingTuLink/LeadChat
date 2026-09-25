"""LLM 模型管理相关 Schema"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    provider: str = "openai"
    model_name: str = Field(min_length=1, max_length=100)
    api_key: str = ""
    api_base: str = ""
    is_active: bool = False

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"openai", "deepseek", "qwen", "glm", "ollama", "custom"}
        v = (v or "openai").strip().lower()
        if v not in allowed:
            raise ValueError(f"厂商必须是 {'/'.join(sorted(allowed))} 之一")
        return v


class ModelUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, max_length=100)
    provider: str | None = None
    model_name: str | None = Field(default=None, max_length=100)
    api_key: str | None = None
    api_base: str | None = None
    is_active: bool | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        allowed = {"openai", "deepseek", "qwen", "glm", "ollama", "custom"}
        v = (v or "").strip().lower()
        if v and v not in allowed:
            raise ValueError(f"厂商必须是 {'/'.join(sorted(allowed))} 之一")
        return v


class ModelOut(BaseModel):
    id: str
    name: str
    provider: str
    model_name: str
    api_key: str
    api_base: str
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


class ModelListResponse(BaseModel):
    models: list[ModelOut]
    total: int


class ProviderListResponse(BaseModel):
    providers: list[dict[str, Any]]
