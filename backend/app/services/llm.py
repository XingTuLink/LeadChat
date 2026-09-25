"""LLM 调用封装：通过 LiteLLM 统一对接 OpenAI / DeepSeek / 通义千问 / 智谱 / Ollama 等

对话模型配置来自后台「模型管理」（数据库，支持多模型在线切换），
调用方必须显式传入激活模型的配置；Embedding 仍由环境变量配置。
"""
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


class ModelNotConfiguredError(RuntimeError):
    """后台未配置/激活对话模型"""


def _chat_target(
    model_cfg: dict,
) -> tuple[str, str | None, str | None]:
    """将后台模型配置解析为 LiteLLM 模型标识。返回 (model, api_key, api_base)"""
    provider = str(model_cfg.get("provider") or "openai").strip().lower()
    model = str(model_cfg.get("model_name") or "").strip()
    api_key = str(model_cfg.get("api_key") or "").strip() or None
    api_base = str(model_cfg.get("api_base") or "").strip() or None

    if not model:
        raise ValueError("模型标识不能为空")

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
        litellm_model = f"openai/{model}"  # 需自行配置 api_base
    else:
        litellm_model = f"openai/{model}"

    return litellm_model, api_key, api_base


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.7,
    model_cfg: dict | None = None,
) -> str:
    """调用大模型，返回回复文本（非流式）

    model_cfg 为后台激活模型的完整配置（含未掩码 api_key）。
    """
    if not model_cfg:
        raise ModelNotConfiguredError("未配置激活模型")
    model, api_key, api_base = _chat_target(model_cfg)
    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        api_key=api_key,
        api_base=api_base,
        timeout=60,
    )
    return response.choices[0].message.content or ""


async def chat_completion_stream(
    messages: list[dict],
    temperature: float = 0.7,
    model_cfg: dict | None = None,
):
    """调用大模型并逐 token 产出文本增量（SSE 流式对话使用）

    yields: 每个 chunk 的增量字符串（可能为空串，调用方可忽略）
    model_cfg 为后台激活模型的完整配置（含未掩码 api_key）。
    """
    if not model_cfg:
        raise ModelNotConfiguredError("未配置激活模型")
    model, api_key, api_base = _chat_target(model_cfg)
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


# ---------------------------------------------------------------- Embedding

def _embedding_target(
    model: str,
) -> tuple[str, str | None, str | None]:
    """解析远程 embedding 模型：含厂商前缀（openai/xxx）直接使用，否则按 OpenAI 处理"""
    m = model.strip()
    litellm_model = m if "/" in m else f"openai/{m}"
    return (
        litellm_model,
        settings.embedding_api_key or None,
        settings.embedding_api_base or None,
    )


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """批量获取文本向量（需配置 EMBEDDING_MODEL）"""
    if not settings.embedding_model:
        raise RuntimeError("EMBEDDING_MODEL 未配置")
    model, api_key, api_base = _embedding_target(settings.embedding_model)
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
