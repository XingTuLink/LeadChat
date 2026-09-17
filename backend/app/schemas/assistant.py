"""Assistant 相关 Schema

注意：Pydantic v2 中 model_config 是 BaseModel 保留属性名，
故 API 字段 model_config 在 Python 侧命名为 model_settings，通过 alias 对外保持 model_config。
"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BusinessFieldIn(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=100)
    type: str = "string"
    options: list[str] = []
    required: bool = False
    sort_order: int = 0

    @field_validator("key")
    @classmethod
    def normalize_key(cls, v: str) -> str:
        v = v.strip().lower()
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("字段标识只能包含字母、数字、下划线、中划线")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"string", "text", "number", "enum", "phone", "email"}
        v = (v or "string").strip().lower()
        if v not in allowed:
            raise ValueError(f"字段类型必须是 {'/'.join(sorted(allowed))} 之一")
        return v


class AssistantCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    scenario: str = "general"
    system_prompt: str | None = None
    model_settings: dict[str, Any] = Field(
        default_factory=dict, validation_alias="model_config"
    )
    context_config: dict[str, Any] | None = None
    collect_config: dict[str, Any] | None = None
    ui_config: dict[str, Any] | None = None
    business_fields: list[BusinessFieldIn] | None = None

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, v: str) -> str:
        allowed = {"general", "support", "internal", "requirement", "sales"}
        v = (v or "general").strip().lower()
        if v not in allowed:
            raise ValueError(f"场景模板必须是 {'/'.join(sorted(allowed))} 之一")
        return v


class AssistantUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    description: str | None = None
    scenario: str | None = None
    system_prompt: str | None = None
    model_settings: dict[str, Any] | None = Field(
        default=None, validation_alias="model_config"
    )
    context_config: dict[str, Any] | None = None
    collect_config: dict[str, Any] | None = None
    ui_config: dict[str, Any] | None = None
    status: str | None = None
    business_fields: list[BusinessFieldIn] | None = None


class AssistantOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str = ""
    scenario: str
    system_prompt: str = ""
    model_settings: dict = Field(
        default_factory=dict,
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    knowledge_config: dict = {"scope": "global"}
    context_config: dict = {}
    collect_config: dict = {}
    ui_config: dict = {}
    business_fields: list[dict] = []
    is_default: bool = False
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None


class AssistantListResponse(BaseModel):
    assistants: list[AssistantOut]
    total: int


class ScenarioOut(BaseModel):
    key: str
    label: str
    description: str
    system_prompt: str = ""
    collect: dict[str, Any] = {}
    fields: list[dict[str, Any]] = []
    context: dict[str, Any] = {}
    ui: dict[str, Any] = {}


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioOut]
