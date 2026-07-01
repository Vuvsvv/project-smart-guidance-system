from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

app = FastAPI(title="Local Voice Gateway")


@app.get("/health")
def health() -> dict:
    return {
        "gateway": "local-windows-tts",
        "services": {
            "chinese_tts": "healthy",
            "taiwanese_tts": "fallback_to_chinese_voice",
            "chinese_asr": "demo_placeholder",
            "taiwanese_asr": "demo_placeholder",
        },
    }


@app.post("/api/process")
def process(
    service_type: str = Form(...),
    text_input: str = Form(""),
    file: Optional[UploadFile] = File(None),
) -> dict:
    if service_type in ("chinese_asr", "taiwanese_asr"):
        return {
            "success": True,
            "service_type": service_type,
            "data": {
                "text": "我不舒服",
                "note": "local demo gateway placeholder; replace with model gateway for real ASR",
            },
        }

    if service_type not in ("chinese_tts", "taiwanese_tts"):
        raise HTTPException(
            status_code=400,
            detail=f"Local gateway only supports TTS. service_type={service_type}",
        )

    text = text_input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text_input is required")

    wav_bytes = _synthesize_with_windows_sapi(text)
    return {
        "success": True,
        "service_type": service_type,
        "data": {
            "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
            "audio_format": "wav",
        },
    }


def _synthesize_with_windows_sapi(text: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "tts.wav"
        script_path = Path(__file__).with_name("synthesize_sapi.ps1")

        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-Text",
                text,
                "-OutputPath",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if completed.returncode != 0 or not output_path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Windows TTS failed: {completed.stderr or completed.stdout}",
            )

        return output_path.read_bytes()
