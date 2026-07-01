"""
語音聊天端點 (/voice/chat)
==========================
把語音接進現有的問診流程（A2 方案）。

流程：
  Android 傳音訊 → ASR 轉文字 → 呼叫現有 chat() 邏輯
                → 拿回覆文字 → TTS 轉語音 → 回傳給 Android

關鍵：完全重用現有的 chat() 函式，不複製問診邏輯。
現有 /chat /recommend /generate_script 完全不動。

容錯：任何語音環節失敗，至少回傳文字，讓 Android 降級用系統 TTS。
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from app.config import get_settings
from app.schemas import ChatRequest, VoiceChatResponse, VoiceTtsRequest, VoiceTtsResponse
from app.routes.chat import chat as chat_handler
from app.services.voice_client import VoiceGatewayClient, VoiceGatewayError

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)


def _get_client() -> VoiceGatewayClient:
    """依設定建立 gateway client"""
    settings = get_settings()
    return VoiceGatewayClient(
        base_url=settings.voice_gateway_url,
        api_key=settings.voice_gateway_key,
        timeout=settings.voice_timeout,
        is_ngrok=settings.voice_gateway_is_ngrok,
    )


@router.post("/chat", response_model=VoiceChatResponse)
async def voice_chat(
    file: UploadFile = File(..., description="長輩說話的音訊檔（wav）"),
    case_id: Optional[str] = Form(None, description="對話 case_id，多輪要帶回來"),
    lang: Optional[str] = Form(None, description="taiwanese（台語）或 chinese（國語）"),
    confirmed: bool = Form(False, description="是否確認分診結果"),
):
    """
    語音版問診：音訊進 → 文字+語音出

    Android 錄音後呼叫這個端點，內部串接 ASR → chat → TTS。
    """
    settings = get_settings()

    # 1. 語音功能開關（Render 上可關掉，本機開）
    if not settings.voice_enabled:
        raise HTTPException(503, "語音功能未啟用（請設定 VOICE_ENABLED=true）")

    # 決定語言（沒傳就用預設）
    use_lang = lang or settings.voice_default_lang
    if use_lang not in ("taiwanese", "chinese"):
        raise HTTPException(400, f"不支援的語言: {use_lang}")

    client = _get_client()

    # 2. ASR：音訊 → 文字
    try:
        audio_bytes = await file.read()
        user_text = client.transcribe(
            audio_bytes, filename=file.filename or "audio.wav", lang=use_lang
        )
    except VoiceGatewayError as e:
        logger.warning("ASR 失敗 case_id=%s: %s", case_id, e)
        raise HTTPException(400, "聽不清楚，請再說一次")

    if not user_text.strip():
        raise HTTPException(400, "聽不清楚，請再說一次")

    logger.info("voice_chat ASR case_id=%s lang=%s user_text=%s", case_id, use_lang, user_text)

    # 3. 呼叫現有 chat 邏輯（重用，不複製）
    chat_req = ChatRequest(case_id=case_id, message=user_text, confirmed=confirmed)
    triage_result = await chat_handler(chat_req)

    reply_text = triage_result.reply or ""

    # 4. TTS：回覆文字 → 語音（失敗就降級回文字）
    reply_audio_base64 = ""
    audio_format = "wav"
    tts_failed = False
    if reply_text.strip():
        try:
            reply_audio_base64 = client.synthesize_base64(reply_text, lang=use_lang)
        except VoiceGatewayError as e:
            logger.warning("TTS 失敗 case_id=%s: %s", triage_result.case_id, e)
            tts_failed = True  # Android 收到後改用系統 TTS 念 reply_text

    # 5. 組回應
    return VoiceChatResponse(
        case_id=triage_result.case_id,
        user_text=user_text,
        reply_text=reply_text,
        reply_audio_base64=reply_audio_base64,
        audio_format=audio_format,
        needMoreInfo=triage_result.needMoreInfo,
        stage=triage_result.conversation_state.stage.value
        if triage_result.conversation_state
        else "",
        department_result=triage_result.department_result,
        tts_failed=tts_failed,
    )


@router.get("/health")
async def voice_health():
    """檢查語音 gateway 是否可用"""
    settings = get_settings()
    if not settings.voice_enabled:
        return {"voice_enabled": False, "message": "語音功能未啟用"}
    try:
        client = _get_client()
        gateway_status = client.health()
        return {"voice_enabled": True, "gateway": gateway_status}
    except VoiceGatewayError as e:
        return {"voice_enabled": True, "gateway": "unreachable", "error": str(e)}


@router.post("/tts", response_model=VoiceTtsResponse)
async def voice_tts(request: VoiceTtsRequest):
    """Convert text to speech through the voice gateway."""
    settings = get_settings()
    if not settings.voice_enabled:
        raise HTTPException(503, "Voice service is disabled. Set VOICE_ENABLED=true.")

    text = request.text.strip()
    if not text:
        raise HTTPException(400, "text is required")

    use_lang = request.lang or "chinese"
    if use_lang not in ("taiwanese", "chinese"):
        raise HTTPException(400, f"Unsupported voice language: {use_lang}")

    try:
        audio_base64 = _get_client().synthesize_base64(
            text,
            lang=use_lang,
            speed=request.speed,
        )
    except VoiceGatewayError as e:
        logger.warning("TTS failed lang=%s: %s", use_lang, e)
        return VoiceTtsResponse(tts_failed=True, error=str(e))

    return VoiceTtsResponse(audio_base64=audio_base64, audio_format="wav")
