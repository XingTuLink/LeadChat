"""对话引擎：组合 Assistant 配置 + LLM + RAG + 业务信息采集的完整对话流程"""
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.message import Message
from app.services import (
    assistant_store,
    config_store,
    context as context_service,
    data_collector,
    llm,
    model_store,
    rag,
)

logger = logging.getLogger("leadchat.chat_engine")


async def get_or_create_conversation(
    session, conversation_id: str | None, website_id: str | None, visitor_id: str | None
) -> Conversation:
    if conversation_id:
        conv = await session.get(Conversation, conversation_id)
        if conv:
            return conv
    conv = Conversation(
        id=uuid.uuid4().hex,
        website_id=website_id,
        visitor_id=visitor_id,
        status="active",
    )
    session.add(conv)
    await session.flush()
    return conv


def build_system_prompt(cfg: dict, sources: list[dict]) -> str:
    """构建系统提示词：基础模板 + RAG 参考资料"""
    prompt = cfg.get("system_prompt") or ""
    replacements = {
        "company_name": cfg.get("company_name") or "我们",
        "business_description": cfg.get("business_description") or "我们的产品与服务",
        "current_date": datetime.now().strftime("%Y-%m-%d"),
    }
    for key, value in replacements.items():
        prompt = prompt.replace("{" + key + "}", value)

    if sources:
        ref_lines = "\n\n".join(
            f"[{i + 1}] (来源: {s.get('filename') or '知识库'})\n{s.get('content', '')}"
            for i, s in enumerate(sources)
        )
        prompt += (
            "\n\n【参考资料】\n" + ref_lines
            + "\n\n请优先依据以上资料回答；资料与问题无关时不要强行引用。"
        )
    else:
        prompt += "\n\n【参考资料】（本次未检索到相关内容，请谨慎回答，不确定的信息要诚实告知。）"
    return prompt


async def _prepare_turn(
    session,
    conversation_id: str | None,
    message: str,
    visitor_id: str | None,
    website_id: str | None,
    assistant_id: str | None,
    context: dict | None,
) -> dict:
    """对话预处理（流式/非流式共用）：会话、助手、上下文、历史、RAG、采集、LLM 消息组装

    用户消息在此阶段已落库（flush），但事务由调用方负责提交。
    """
    conv = await get_or_create_conversation(session, conversation_id, website_id, visitor_id)

    # 0. 解析助手（缺省/停用/不存在 → 默认助手），叠加运行时配置
    assistant = await assistant_store.resolve_assistant(
        session, assistant_id or conv.assistant_id
    )
    conv.assistant_id = assistant.id
    global_cfg = await config_store.get_all_config(session)
    cfg = await assistant_store.runtime_config(session, assistant, global_cfg)

    # 0.05 当前激活的全局对话模型（未配置时对话无法进行）
    active_model = await model_store.get_active(session)
    if active_model is None:
        raise llm.ModelNotConfiguredError("后台未配置激活的对话模型")
    model_cfg = model_store.to_dict(active_model, masked=False)

    # 0.1 业务上下文：白名单清洗后随对话持久化并注入 Prompt
    safe_context = context_service.sanitize_context(
        context, assistant_store.get_context_config(assistant)
    )
    if safe_context:
        conv.context_json = json.dumps(safe_context, ensure_ascii=False)
    elif context:
        # 宿主显式传了但全被过滤，也覆盖旧值，避免残留过期上下文
        conv.context_json = None

    # 1. 读取历史（最近 N 轮）
    rows = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id.desc())
            .limit(settings.history_rounds * 2)
        )
    ).scalars().all()[::-1]
    history = [
        {"role": r.role, "content": r.content}
        for r in rows
        if r.role in ("user", "assistant")
    ]

    # 2. 保存用户消息
    session.add(Message(conversation_id=conv.id, role="user", content=message))

    # 3. RAG 检索（本期知识库为全局共享，知识源范围在模型中已预留）
    try:
        sources = await rag.search(message)
    except Exception as e:
        logger.warning("RAG 检索失败: %s", e)
        sources = []

    # 4. 对话式业务数据采集（ASK 模式直接跳过）
    collection = await data_collector.run_collection(
        session, conv, message, history, cfg, assistant
    )

    # 5. 调用 LLM 生成回复：Instructions + Business Context + RAG + 采集指令 + History
    system_prompt = build_system_prompt(cfg, sources)
    system_prompt = context_service.inject_context(system_prompt, safe_context)
    system_prompt += data_collector.build_collection_instruction(collection, cfg)
    llm_messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": message}]
    )
    return {
        "conv": conv,
        "assistant": assistant,
        "sources": sources,
        "collection": collection,
        "llm_messages": llm_messages,
        "model_cfg": model_cfg,
    }


def _result_payload(prepared: dict, reply: str) -> dict:
    """组装对话接口统一响应（流式 done 事件与非流式响应共用）"""
    conv, assistant, sources, collection = (
        prepared["conv"], prepared["assistant"], prepared["sources"], prepared["collection"]
    )
    captured = collection.get("stage") == "captured"
    return {
        "conversation_id": conv.id,
        "assistant_id": assistant.id,
        "reply": reply,
        "sources": sources,
        # 通用采集结果（data_type 可为 lead/ticket/requirement/appointment/custom）
        "data_captured": captured,
        "data_type": collection.get("data_type") if captured else None,
    }


async def process_message(
    conversation_id: str | None,
    message: str,
    visitor_id: str | None = None,
    website_id: str | None = None,
    assistant_id: str | None = None,
    context: dict | None = None,
) -> dict:
    """处理一条用户消息，返回 AI 回复与业务信息采集状态（非流式）"""
    async with AsyncSessionLocal() as session:
        try:
            prepared = await _prepare_turn(
                session, conversation_id, message, visitor_id, website_id, assistant_id, context
            )
        except llm.ModelNotConfiguredError:
            # 未配置/激活模型：本次会话不提交，返回友好提示
            return {
                "conversation_id": None,
                "assistant_id": "default",
                "reply": "抱歉，AI 助手尚未配置完成，请稍后再试。",
                "sources": [],
                "data_captured": False,
                "data_type": None,
            }
        try:
            reply = await llm.chat_completion(
                prepared["llm_messages"], model_cfg=prepared["model_cfg"]
            )
        except llm.ModelNotConfiguredError:
            reply = "抱歉，AI 助手尚未配置完成，请稍后再试。"
        except Exception as e:
            logger.exception("LLM 调用失败: %s", e)
            reply = "抱歉，AI服务暂时不可用，请稍后再试。"

        # 6. 保存 AI 消息并提交
        conv = prepared["conv"]
        session.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=reply,
                sources=prepared["sources"] or None,
            )
        )
        conv.updated_at = datetime.now()
        await session.commit()

        return _result_payload(prepared, reply)


async def process_message_stream(
    conversation_id: str | None,
    message: str,
    visitor_id: str | None = None,
    website_id: str | None = None,
    assistant_id: str | None = None,
    context: dict | None = None,
):
    """流式处理一条用户消息。

    产出 (event, data) 二元组：
      ("meta",  {conversation_id, assistant_id})  —— 首个事件，可立即确定会话
      ("delta", {content})                        —— 逐 token 文本增量
      ("done",  {reply, sources, data_captured, …})—— 完整回复与采集结果
      ("error", {message})                        —— 预处理阶段致命错误
    客户端断开时生成器被取消，已生成的部分回复仍尽力落库（finally 提交）。
    """
    async with AsyncSessionLocal() as session:
        try:
            prepared = await _prepare_turn(
                session, conversation_id, message, visitor_id, website_id, assistant_id, context
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("流式对话预处理失败: %s", e)
            yield "error", {"message": "服务暂时不可用，请稍后再试。"}
            return

        conv = prepared["conv"]
        yield "meta", {"conversation_id": conv.id, "assistant_id": prepared["assistant"].id}

        parts: list[str] = []
        committed = False

        async def _persist(text: str) -> None:
            session.add(
                Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=text,
                    sources=prepared["sources"] or None,
                )
            )
            conv.updated_at = datetime.now()
            await session.commit()

        try:
            stream_failed = False
            try:
                async for piece in llm.chat_completion_stream(
                    prepared["llm_messages"], model_cfg=prepared["model_cfg"]
                ):
                    parts.append(piece)
                    yield "delta", {"content": piece}
            except Exception as e:  # noqa: BLE001
                logger.exception("LLM 流式调用失败: %s", e)
                stream_failed = True

            if stream_failed:
                if parts:
                    # 已有部分输出：保留已产出内容，追加降级提示，不假装完整
                    parts.append("\n\n（连接中断，回复可能不完整，请重试）")
                    yield "delta", {"content": "\n\n（连接中断，回复可能不完整，请重试）"}
                else:
                    fallback = "抱歉，AI服务暂时不可用，请稍后再试。"
                    parts.append(fallback)
                    yield "delta", {"content": fallback}

            reply = "".join(parts)
            try:
                await _persist(reply)
            except Exception as e:  # noqa: BLE001
                logger.exception("流式回复落库失败: %s", e)
            committed = True
            yield "done", _result_payload(prepared, reply)
        finally:
            # 客户端中途断开（GeneratorExit）：尽力把已产出的部分回复落库，此处不允许再 yield
            if not committed and parts:
                try:
                    await _persist("".join(parts))
                except Exception as e:  # noqa: BLE001
                    logger.warning("断连后部分回复落库失败: %s", e)
