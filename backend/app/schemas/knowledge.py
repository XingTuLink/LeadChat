"""知识库相关 Schema"""
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    filename: str
    file_type: str
    chunk_count: int
    created_at: datetime | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]


class SearchResult(BaseModel):
    content: str
    doc_id: str | None = None
    filename: str = ""
    score: float | None = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
