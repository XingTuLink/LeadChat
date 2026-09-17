"""LLM 调用封装：通过 LiteLLM 统一对接 OpenAI / DeepSeek / 通义千问 / 智谱 / Ollama 等"""
import logging

import litellm

from app.config import settings

logger = logging.getLogger("leadchat.llm")

try:
    litellm.suppress_debug_info = True
except Exception:  # noqa: S110
    pass

# 各厂商默认的 OpenAI 兼容端点
PROVIDER_DEFAULT_BASES = {
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "ollama": "http://localhost:11434",
}


def _resolve(model: str | None = None) -> tuple[str, str | None, str | None]:
    """解析为 LiteLLM 模型标识。返回 (model, api_key, api_base)"""
    provider = (settings.llm_provider or "openai").strip().lower()
    model = (model or settings.llm_model).strip()
    api_key = settings.llm_api_key or None
    api_base = settings.llm_api_base or None

    if provider in ("", "openai"):
        litellm_model = model if model.startswith("openai/") else f"openai/{model}"
    elif provider == "deepseek":
        litellm_model = f"deepseek/{model}"
    elif provider == "qwen":
        litellm_model = f"openai/{model}"
        api_base = api_base or PROVIDER_DEFAULT_BASES["qwen"]
    elif provider == "glm":
        litellm_model = f"openai/{model}"
        api_base = api_base or PROVIDER_DEFAULT_BASES["glm"]
    elif provider == "ollama":
        litellm_model = f"ollama/{model}"
        api_base = api_base or PROVIDER_DEFAULT_BASES["ollama"]
    elif provider in ("custom", "openai_compatible", "compatible"):
        litellm_model = f"openai/{model}"  # 需自行配置 LLM_API_BASE
    else:
        litellm_model = f"openai/{model}"

    return litellm_model, api_key, api_base


async def chat_completion(messages: list[dict], temperature: float = 0.7) -> str:
    """调用大模型，返回回复文本（非流式）"""
    model, api_key, api_base = _resolve()
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        api_key=api_key,
        api_base=api_base,
        timeout=60,
    )
    return response.choices[0].message.content or ""


async def chat_completion_stream(messages: list[dict], temperature: float = 0.7):
    """调用大模型并逐 token 产出文本增量（SSE 流式对话使用）

    yields: 每个 chunk 的增量字符串（可能为空串，调用方可忽略）
    """
    model, api_key, api_base = _resolve()
    stream = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        api_key=api_key,
        api_base=api_base,
        timeout=60,
        stream=True,
    )
    try:
        async for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            piece = getattr(delta, "content", None) if delta else None
            if piece:
                yield piece
    finally:
        close = getattr(stream, "aclose", None)
        if close is not None:
            try:
                await close()
            except Exception:  # noqa: BLE001
                pass


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """批量获取文本向量（需配置 EMBEDDING_MODEL）"""
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL 未配置")
    model, api_key, api_base = _resolve(settings.embedding_model)
    response = await litellm.aembedding(
        model=model,
        input=texts,
        api_key=api_key,
        api_base=api_base,
        timeout=60,
    )
    data = sorted(response.data, key=lambda x: x.get("index", 0))
    return [d["embedding"] for d in data]


async def get_embedding(text: str) -> list[float]:
    """获取单条文本向量"""
    return (await get_embeddings([text]))[0]
