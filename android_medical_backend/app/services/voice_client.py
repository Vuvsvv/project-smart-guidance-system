"""
語音 Gateway 客戶端
==================
呼叫語音 gateway 的統一入口（POST /api/process）。

這是一個獨立的工具類別，不依賴後端任何現有邏輯。
後端需要語音時 import 來用即可。

gateway 提供四個服務（用 service_type 區分）：
  taiwanese_asr  台語語音 → 中文字
  chinese_asr    國語語音 → 中文字
  taiwanese_tts  中文字 → 台語語音
  chinese_tts    中文字 → 國語語音

用法：
    client = VoiceGatewayClient(base_url="https://xxx.ngrok-free.dev",
                                api_key="your_key")

    # 語音轉文字（lang 決定台語或國語）
    text = client.transcribe(audio_bytes, filename="a.wav", lang="taiwanese")

    # 文字轉語音（回傳 wav bytes）
    wav = client.synthesize("你好", lang="chinese")
"""

from __future__ import annotations

import base64
import logging
from typing import Literal, Optional

import requests

logger = logging.getLogger(__name__)

Lang = Literal["taiwanese", "chinese"]


class VoiceGatewayError(Exception):
    """gateway 呼叫失敗時拋出"""
    pass


class VoiceGatewayClient:
    """語音 gateway 客戶端"""

    # lang → service_type 對照
    _ASR_SERVICE = {
        "taiwanese": "taiwanese_asr",
        "chinese": "chinese_asr",
    }
    _TTS_SERVICE = {
        "taiwanese": "taiwanese_tts",
        "chinese": "chinese_tts",
    }

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 120.0,
        is_ngrok: bool = True,
    ):
        """
        Args:
            base_url: gateway 網址（例如 https://xxx.ngrok-free.dev，結尾不用斜線）
            api_key: gateway 的 X-API-Key
            timeout: 請求逾時秒數（TTS 在 CPU 上較慢，預設給寬一點）
            is_ngrok: 走 ngrok 時自動帶上跳過警告頁的 header
        """
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/api/process"
        self.timeout = timeout

        self.headers = {"X-API-Key": api_key}
        if is_ngrok:
            self.headers["ngrok-skip-browser-warning"] = "true"

    # ── 語音轉文字（ASR）──
    def transcribe(
        self,
        audio: bytes,
        filename: str = "audio.wav",
        lang: Lang = "taiwanese",
    ) -> str:
        """
        語音 → 中文字

        Args:
            audio: 音訊檔的 bytes
            filename: 檔名（gateway 用來判斷格式）
            lang: "taiwanese"（台語）或 "chinese"（國語）

        Returns:
            辨識出的中文字串

        Raises:
            VoiceGatewayError: 呼叫失敗或 gateway 回報錯誤
        """
        service_type = self._ASR_SERVICE.get(lang)
        if not service_type:
            raise VoiceGatewayError(f"不支援的語言: {lang}")

        try:
            resp = requests.post(
                self.endpoint,
                headers=self.headers,
                files={"file": (filename, audio, "audio/wav")},
                data={"service_type": service_type},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise VoiceGatewayError(f"連線 gateway 失敗: {e}") from e

        payload = self._parse(resp, service_type)
        text = payload.get("data", {}).get("text", "")
        if not text:
            logger.warning("ASR 回傳空字串 service_type=%s", service_type)
        return text.strip()

    # ── 文字轉語音（TTS）──
    def synthesize(
        self,
        text: str,
        lang: Lang = "chinese",
        speed: float = 1.0,
    ) -> bytes:
        """
        中文字 → 語音

        Args:
            text: 要合成的中文字
            lang: "taiwanese"（台語）或 "chinese"（國語）
            speed: 語速

        Returns:
            wav 音訊的 bytes（可直接寫檔或回傳給 Android 播放）

        Raises:
            VoiceGatewayError: 呼叫失敗或 gateway 回報錯誤
        """
        service_type = self._TTS_SERVICE.get(lang)
        if not service_type:
            raise VoiceGatewayError(f"不支援的語言: {lang}")
        if not text.strip():
            raise VoiceGatewayError("text 不可為空")

        data = {
            "service_type": service_type,
            "text_input": text,
        }
        if speed != 1.0:
            import json
            data["extra_params"] = json.dumps({"speed": speed})

        try:
            resp = requests.post(
                self.endpoint,
                headers=self.headers,
                data=data,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise VoiceGatewayError(f"連線 gateway 失敗: {e}") from e

        payload = self._parse(resp, service_type)
        data = payload.get("data", {})
        audio_b64 = data.get("audio_base64", "")
        if not audio_b64:
            # 把下游服務回的完整內容顯示出來，方便除錯
            raise VoiceGatewayError(
                f"TTS 未回傳音訊 service_type={service_type}，"
                f"gateway data={data}"
            )

        try:
            return base64.b64decode(audio_b64)
        except Exception as e:
            raise VoiceGatewayError(f"音訊 base64 解碼失敗: {e}") from e

    # ── 文字轉語音，回傳 base64 字串（給 Android 直接用）──
    def synthesize_base64(
        self,
        text: str,
        lang: Lang = "chinese",
        speed: float = 1.0,
    ) -> str:
        """
        同 synthesize，但直接回傳 base64 字串。
        給 /voice/chat 端點回傳給 Android 時用，省去再編碼一次。
        """
        wav = self.synthesize(text, lang=lang, speed=speed)
        return base64.b64encode(wav).decode("utf-8")

    # ── 健康檢查 ──
    def health(self) -> dict:
        """
        檢查 gateway 和各服務狀態。
        回傳 gateway 的 /health JSON。
        """
        try:
            resp = requests.get(
                f"{self.base_url}/health",
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise VoiceGatewayError(f"健康檢查失敗: {e}") from e

    # ── 內部：解析 gateway 回應 ──
    def _parse(self, resp: requests.Response, service_type: str) -> dict:
        """檢查 HTTP 狀態 + gateway 的 success 欄位"""
        if resp.status_code != 200:
            raise VoiceGatewayError(
                f"gateway HTTP {resp.status_code} "
                f"(service_type={service_type}): {resp.text[:200]}"
            )

        try:
            payload = resp.json()
        except ValueError as e:
            raise VoiceGatewayError(
                f"gateway 回應非 JSON: {resp.text[:200]}"
            ) from e

        if not payload.get("success", False):
            error = payload.get("error", "未知錯誤")
            raise VoiceGatewayError(
                f"gateway 回報失敗 (service_type={service_type}): {error}"
            )

        return payload


# ── 單獨測試用 ──
# 直接執行這個檔案就能測 client 能不能連上你的 gateway：
#   python voice_client.py
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    # ↓↓↓ 改成你的 ngrok 網址和 key ↓↓↓
    GATEWAY_URL = "https://你的網址.ngrok-free.dev"
    API_KEY = "你的key"

    print("=" * 50)
    print("語音 Gateway Client 連線測試")
    print("=" * 50)

    client = VoiceGatewayClient(base_url=GATEWAY_URL, api_key=API_KEY)

    # 1. 健康檢查
    print("\n[1] 健康檢查...")
    try:
        h = client.health()
        print(f"  gateway: {h.get('gateway')}")
        for name, status in h.get("services", {}).items():
            mark = "✅" if status == "healthy" else "❌"
            print(f"  {mark} {name}: {status}")
    except VoiceGatewayError as e:
        print(f"  ❌ 失敗: {e}")
        sys.exit(1)

    # 2. TTS 測試（國語）
    print("\n[2] 國語 TTS 測試...")
    try:
        wav = client.synthesize("你好，這是測試", lang="chinese")
        with open("test_chinese_tts.wav", "wb") as f:
            f.write(wav)
        print(f"  ✅ 國語語音已存成 test_chinese_tts.wav ({len(wav)} bytes)")
    except VoiceGatewayError as e:
        print(f"  ❌ 失敗: {e}")

    # 3. TTS 測試（台語）
    print("\n[3] 台語 TTS 測試...")
    try:
        wav = client.synthesize("你好", lang="taiwanese")
        with open("test_taiwanese_tts.wav", "wb") as f:
            f.write(wav)
        print(f"  ✅ 台語語音已存成 test_taiwanese_tts.wav ({len(wav)} bytes)")
    except VoiceGatewayError as e:
        print(f"  ❌ 失敗: {e}")

    # 4. ASR 測試（如果有測試音檔）
    print("\n[4] ASR 測試（需要 test_input.wav）...")
    import os
    if os.path.exists("test_input.wav"):
        try:
            with open("test_input.wav", "rb") as f:
                audio = f.read()
            text = client.transcribe(audio, lang="taiwanese")
            print(f"  ✅ 辨識結果: {text}")
        except VoiceGatewayError as e:
            print(f"  ❌ 失敗: {e}")
    else:
        print("  （跳過，沒有 test_input.wav）")

    print("\n測試完成。")
