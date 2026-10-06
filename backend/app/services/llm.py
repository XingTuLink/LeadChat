"""LLM 调用封装：通过 LiteLLM 统一对接 OpenAI / DeepSeek / 通义千问 / 智谱 / Ollama 等

对话模型配置来自后台「模型管理」（数据库，支持多模型在线切换），
调用方必须显式传入激活模型的配置。
Embedding 使用内置本地模型（ChromaDB ONNX），无需任何配置。
"""
import logging

import litellm

from app.services.model_store import PROVIDER_DEFAULT_BASES

logger = logging.getLogger("leadchat.llm")

try:
    litellm.suppress_debug_info = True
except Exception:  # noqa: S110
    pass


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
        raise ValueError("模型不能为空")

    if provider in ("", "openai"):
        # OpenAI 官方：LiteLLM 内置默认端点，api_base 留空即可
        litellm_model = model if model.startswith("openai/") else f"openai/{model}"
    elif provider == "deepseek":
        # DeepSeek 官方：LiteLLM 原生支持
        litellm_model = f"deepseek/{model}"
    elif provider in ("qwen", "glm", "ollama"):
        # 走各厂商 / 本地服务的 OpenAI 兼容端点
        litellm_model = f"openai/{model}" if provider != "ollama" else f"ollama/{model}"
        api_base = api_base or PROVIDER_DEFAULT_BASES[provider]
    elif provider in ("custom", "openai_compatible", "compatible"):
        # 自建 / 第三方 OpenAI 兼容服务（vLLM、内网网关等），必须提供端点
        if not api_base:
            raise ValueError("OpenAI 兼容服务必须填写接口端点")
        litellm_model = f"openai/{model}"
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
