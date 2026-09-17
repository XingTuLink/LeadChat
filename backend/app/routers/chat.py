"""对话接口：挂件公开消息收发 + 管理端对话记录查询"""
import json
import uuid
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.assistant import CollectedData
from app.models.conversation import Conversation
from app.models.knowledge import KnowledgeDocument
from app.models.message import Message
from app.routers.auth import verify_admin
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationListResponse,
    ConversationOut,
    CreateConversationRequest,
    CreateConversationResponse,
    MessageListResponse,
    MessageOut,
    StatsResponse,
)
from app.services.chat_engine import process_message, process_message_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _auto_close_stale(db: AsyncSession) -> None:
    """闲置超时的对话自动置为「已结束」（管理端查询前惰性执行）"""
    minutes = settings.conversation_timeout_minutes
    if minutes <= 0:
        return
    deadline = datetime.now() - timedelta(minutes=minutes)
    await db.execute(
        update(Conversation)
        .where(Conversation.status == "active", Conversation.updated_at < deadline)
        .values(status="closed")
    )
    await db.commit()


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(body: ChatMessageRequest):
    """访客发送消息（挂件使用，无需鉴权）

    支持可选 assistant_id（指定助手）与 context（宿主业务上下文），
    不传时行为与旧版完全一致（默认助手 + 无上下文）。
    """
    return await process_message(
        conversation_id=body.conversation_id,
        message=body.message.strip(),
        visitor_id=body.visitor_id,
        assistant_id=body.assistant_id,
        context=body.context,
    )


# SSE 事件协议（与挂件 fetch+ReadableStream 对接）：
#   event: meta  → {"conversation_id","assistant_id"}（首个事件）
#   event: delta → {"content"}（逐 token 增量）
#   event: done  → 与非流式 /message 完全一致的完整响应
#   event: error → {"message"}（预处理失败，调用方应回退非流式）
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # 关闭 Nginx 反代缓冲，保证增量即时下发
    "Connection": "keep-alive",
}


@router.post("/message/stream")
async def send_message_stream(body: ChatMessageRequest):
    """访客发送消息（SSE 流式，挂件使用，无需鉴权）

    请求体与 /message 完全相同；LLM 回复按 token 分片推送，
    RAG / 业务采集 / 落库等行为与非流式接口一致。
    """

    async def event_generator():
        async for event, data in process_message_stream(
            conversation_id=body.conversation_id,
            message=body.message.strip(),
            visitor_id=body.visitor_id,
            assistant_id=body.assistant_id,
            context=body.context,
        ):
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/conversation", response_model=CreateConversationResponse)
async def create_conversation(body: CreateConversationRequest, db: AsyncSession = Depends(get_db)):
    """创建新对话（挂件使用，无需鉴权）"""
    from app.services import assistant_store, context as context_service

    assistant = await assistant_store.resolve_assistant(db, body.assistant_id)
    safe_context = context_service.sanitize_context(
        body.context, assistant_store.get_context_config(assistant)
    )
    conv = Conversation(
        id=uuid.uuid4().hex,
        website_id=body.website_id,
        visitor_id=body.visitor_id,
        assistant_id=assistant.id,
        context_json=json.dumps(safe_context, ensure_ascii=False) if safe_context else None,
        status="active",
    )
    db.add(conv)
    await db.commit()
    return {"conversation_id": conv.id, "assistant_id": assistant.id}


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    _: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """对话列表（管理端）"""
    await _auto_close_stale(db)
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    stmt = select(Conversation).order_by(Conversation.updated_at.desc())
    count_stmt = select(func.count()).select_from(Conversation)
    if status:
        stmt = stmt.where(Conversation.status == status)
        count_stmt = count_stmt.where(Conversation.status == status)
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return {"conversations": [ConversationOut.model_validate(r) for r in rows], "total": total}


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """对话消息列表（挂件恢复历史 + 管理端查看）"""
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
        )
    ).scalars().all()
    return {"messages": [MessageOut.model_validate(r) for r in rows]}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    _: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除对话及其全部消息（管理端）"""
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    # 解绑该对话产生的采集数据（记录保留，仅断开关联）
    await db.execute(
        update(CollectedData)
        .where(CollectedData.conversation_id == conversation_id)
        .values(conversation_id=None)
    )
    await db.delete(conv)
    await db.commit()
    return {"success": True}


@router.put("/conversations/{conversation_id}/close")
async def close_conversation(
    conversation_id: str,
    _: bool = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """手动结束对话（管理端）"""
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    conv.status = "closed"
    await db.commit()
    return {"success": True}


@router.get("/stats", response_model=StatsResponse)
async def get_stats(_: bool = Depends(verify_admin), db: AsyncSession = Depends(get_db)):
    """仪表盘统计数据（管理端）"""
    await _auto_close_stale(db)
    today_start = datetime.combine(datetime.now().date(), time.min)
    total_conversations = (await db.execute(select(func.count()).select_from(Conversation))).scalar() or 0
    today_conversations = (
        await db.execute(
            select(func.count()).select_from(Conversation).where(Conversation.created_at >= today_start)
        )
    ).scalar() or 0
    total_messages = (await db.execute(select(func.count()).select_from(Message))).scalar() or 0
    total_collected = (
        await db.execute(select(func.count()).select_from(CollectedData))
    ).scalar() or 0
    today_collected = (
        await db.execute(
            select(func.count()).select_from(CollectedData).where(CollectedData.created_at >= today_start)
        )
    ).scalar() or 0
    total_documents = (await db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar() or 0
    return {
        "today_conversations": today_conversations,
        "today_collected": today_collected,
        "total_conversations": total_conversations,
        "total_collected": total_collected,
        "total_messages": total_messages,
        "total_documents": total_documents,
    }
