import asyncio
from typing import Any, List
import logging

from app.config import get_settings

_initialized = False
_llama_settings: Any = None
_google_client: Any = None
logger = logging.getLogger(__name__)

def initialize_ai() -> None:
    global _google_client, _initialized, _llama_settings
    if _initialized:
        return

    settings = get_settings()
    if not settings.google_api_key:
        logger.info("AI initialization skipped: GOOGLE_API_KEY is not configured")
        return

    if _is_render_free_mode(settings):
        try:
            from google import genai
        except ImportError as exc:
            logger.warning("Lightweight Gemini client is unavailable: %s", exc)
            return

        _google_client = genai.Client(api_key=settings.google_api_key)
        _initialized = True
        logger.info("AI initialized in lightweight Gemini mode")
        return

    try:
        from llama_index.core import Settings as LlamaSettings
        from llama_index.llms.google_genai import GoogleGenAI

        LlamaSettings.llm = GoogleGenAI(
            model=settings.llm_model,
            api_key=settings.google_api_key,
        )
        if not settings.disable_local_embedding:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding

            LlamaSettings.embed_model = HuggingFaceEmbedding(model_name=settings.embedding_model)
        _llama_settings = LlamaSettings
    except ImportError as exc:
        logger.warning("Full AI stack is unavailable; falling back to lightweight Gemini if possible: %s", exc)
        try:
            from google import genai
        except ImportError as google_exc:
            logger.warning("Lightweight Gemini client is unavailable: %s", google_exc)
            return
        _google_client = genai.Client(api_key=settings.google_api_key)
    _initialized = True

def build_chat_prompt(messages: List[dict]) -> str:
    system = (
        "你是 AI 智慧醫療掛號導引系統中的對話助手。"
        "請用簡潔中文回覆病患。必要時請進行多輪問答以確認關鍵資訊，"
        "如果目前資訊不足，請直接提出下一個補充問題。"
        "不要輸出思考過程或額外備註。"
    )
    conversation = "\n".join(
        f"{message['role'].capitalize()}: {message['content'].strip()}"
        for message in messages
        if message['content'].strip()
    )
    return f"{system}\n\n{conversation}\n\nAssistant:"

async def ask_follow_up(messages: List[dict]) -> str:
    prompt = build_chat_prompt(messages)
    return await complete_prompt(prompt)

async def complete_prompt(prompt: str) -> str:
    initialize_ai()
    settings = get_settings()
    if _llama_settings is not None and getattr(_llama_settings, "llm", None) is not None:
        response = await asyncio.wait_for(
            _llama_settings.llm.acomplete(prompt),
            timeout=settings.ai_timeout_seconds,
        )
        return str(response).strip()
    if _google_client is not None:
        response = await asyncio.wait_for(
            _google_client.aio.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
            ),
            timeout=settings.ai_timeout_seconds,
        )
        return str(getattr(response, "text", response)).strip()
    raise RuntimeError("AI is not initialized")


def _is_render_free_mode(settings: Any) -> bool:
    return (
        settings.deploy_mode.lower() == "render_free"
        or settings.disable_local_embedding
    )
