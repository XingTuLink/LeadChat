"""知识库管理接口（管理端）"""
import asyncio
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.knowledge import KnowledgeDocument
from app.routers.auth import verify_admin
from app.schemas.knowledge import DocumentListResponse, DocumentOut, SearchResponse
from app.services import rag
from app.services.document import SUPPORTED_TYPES, parse_file, save_upload
from app.utils.text_splitter import split_text

logger = logging.getLogger("leadchat.knowledge")

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"], dependencies=[Depends(verify_admin)])


@router.post("/upload", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """上传文档：解析 → 切片 → 向量化入库"""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅支持：{', '.join(sorted(SUPPORTED_TYPES))}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 20MB")

    try:
        path = save_upload(filename, data)
        text = await asyncio.to_thread(parse_file, path, ext)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("文档解析失败: %s", e)
        raise HTTPException(status_code=400, detail=f"文件解析失败：{e}")

    if not text.strip():
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="未能从文件中提取到文本内容")

    chunks = split_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="文档内容为空，无法建立索引")

    doc = KnowledgeDocument(
        filename=filename, content=text, file_path=str(path), file_type=ext, chunk_count=len(chunks)
    )
    db.add(doc)
    await db.flush()

    try:
        await rag.add_documents(str(doc.id), chunks, filename=filename)
    except Exception as e:
        logger.exception("向量索引失败: %s", e)
        await db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"向量索引失败：{e}")

    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(db: AsyncSession = Depends(get_db)):
    """文档列表"""
    rows = (
        await db.execute(select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()))
    ).scalars().all()
    return {"documents": [DocumentOut.model_validate(r) for r in rows]}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """删除文档：同时清理向量与文件"""
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        await rag.delete_documents(str(document_id))
    except Exception as e:
        logger.warning("清理向量失败（继续删除记录）: %s", e)
    if doc.file_path:
        from pathlib import Path

        Path(doc.file_path).unlink(missing_ok=True)
    await db.delete(doc)
    await db.commit()
    return {"success": True}


@router.get("/search", response_model=SearchResponse)
async def search_knowledge(
    query: str = Query(min_length=1),
    top_k: int = Query(default=3, ge=1, le=20),
):
    """知识库语义检索（调试用）"""
    results = await rag.search(query, top_k=top_k)
    return {"results": results}
