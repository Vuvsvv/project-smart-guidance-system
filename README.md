# Android Medical AI Guidance

Android Jetpack Compose frontend with a FastAPI backend for AI triage, doctor recommendation, booking-script generation, and voice integration.

This branch contains the current voice integration handoff state. It is meant to help backend teammates continue from a known working local setup.

## Project Layout

```text
.
├── app/                         # Android app
├── android_medical_backend/     # FastAPI backend
├── gradle/
├── build.gradle.kts
├── settings.gradle.kts
└── README.md
```

## Current Voice Behavior

### ChatScreen Language Modes

- `國語`
  - Microphone uses Android built-in speech recognition (`RecognizerIntent`).
  - Message playback calls backend `/voice/tts` with `lang = "chinese"`.
  - Backend forwards to gateway `service_type = chinese_tts`.

- `台語`
  - Microphone switches to app recording mode.
  - First tap starts recording, second tap stops and uploads a WAV file.
  - Upload target: backend `/voice/chat` with `lang = "taiwanese"`.
  - Backend forwards ASR to gateway `service_type = taiwanese_asr`.
  - Message playback calls backend `/voice/tts` with `lang = "taiwanese"`.
  - Backend forwards TTS to gateway `service_type = taiwanese_tts`.

### Important Current Limitation

The real model gateway from the teammate/school machine is not included here.

For local demo, this branch includes a lightweight compatible gateway:

```text
android_medical_backend/local_voice_gateway.py
android_medical_backend/synthesize_sapi.ps1
```

It provides the same gateway endpoints:

```text
GET  /health
POST /api/process
```

It can generate playable WAV audio using Windows built-in SAPI TTS, so `chinese_tts` and `taiwanese_tts` can be tested end-to-end.

Its ASR is only a placeholder:

```text
taiwanese_asr -> returns "我不舒服"
chinese_asr   -> returns "我不舒服"
```

Replace this local gateway with the real model gateway for real Taiwanese ASR/TTS.

## Backend APIs

Backend base URL for local phone testing is currently set in:

```text
app/src/main/java/com/example/medicalaiguidance/network/MedicalApiClient.kt
```

Current value:

```kotlin
const val DEFAULT_BASE_URL = "http://192.168.50.63:8080"
```

Update this IP when testing on another computer/network.

Backend endpoints:

```text
POST /chat
POST /recommend
POST /generate_script
POST /voice/chat
POST /voice/tts
GET  /voice/health
```

Voice gateway contract used by backend:

```text
POST {VOICE_GATEWAY_URL}/api/process
Header: X-API-Key: {VOICE_GATEWAY_KEY}
```

Gateway `service_type` mapping:

```text
taiwanese_asr
chinese_asr
taiwanese_tts
chinese_tts
```

## Local Run

Use two terminals.

### 1. Start Compatible Local Gateway

```powershell
cd android_medical_backend
python -m uvicorn local_voice_gateway:app --host 0.0.0.0 --port 8000
```

Check:

```text
http://127.0.0.1:8000/health
```

### 2. Start Backend

Create `android_medical_backend/.env`:

```env
VOICE_ENABLED=true
VOICE_GATEWAY_URL=http://localhost:8000
VOICE_GATEWAY_KEY=sk-secret-key-here
VOICE_GATEWAY_IS_NGROK=false
VOICE_DEFAULT_LANG=taiwanese
VOICE_TIMEOUT=120

GOOGLE_API_KEY=
DB_PASSWORD=
DEPLOY_MODE=local
DISABLE_LOCAL_EMBEDDING=true
```

Install dependencies:

```powershell
cd android_medical_backend
python -m pip install -r requirements.txt
```

Start backend on `8080`:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Check:

```text
http://127.0.0.1:8080/docs
http://127.0.0.1:8080/voice/health
```

Expected `/voice/health` with compatible local gateway:

```json
{
  "voice_enabled": true,
  "gateway": {
    "gateway": "local-windows-tts",
    "services": {
      "chinese_tts": "healthy",
      "taiwanese_tts": "fallback_to_chinese_voice",
      "chinese_asr": "demo_placeholder",
      "taiwanese_asr": "demo_placeholder"
    }
  }
}
```

## Android Build

```powershell
.\gradlew.bat assembleDebug
```

Debug APK:

```text
app/build/outputs/apk/debug/app-debug.apk
```

## Key Frontend Files

```text
app/src/main/AndroidManifest.xml
app/src/main/java/com/example/medicalaiguidance/screen/ChatScreen.kt
app/src/main/java/com/example/medicalaiguidance/viewmodel/ChatViewModel.kt
app/src/main/java/com/example/medicalaiguidance/repository/MedicalRepository.kt
app/src/main/java/com/example/medicalaiguidance/network/MedicalApiClient.kt
app/src/main/java/com/example/medicalaiguidance/network/MedicalDtos.kt
app/src/main/java/com/example/medicalaiguidance/util/AudioRecorder.kt
app/src/main/java/com/example/medicalaiguidance/util/AudioPlayer.kt
```

## Key Backend Files

```text
android_medical_backend/app/main.py
android_medical_backend/app/routes/voice.py
android_medical_backend/app/services/voice_client.py
android_medical_backend/app/schemas.py
android_medical_backend/app/config.py
android_medical_backend/local_voice_gateway.py
android_medical_backend/synthesize_sapi.ps1
```

## Cleanup Done

Unused old flow files were removed:

```text
app/src/main/java/com/example/medicalaiguidance/state/TriageFlowController.kt
app/src/main/java/com/example/medicalaiguidance/screen/VoiceInput1Screen.kt
app/src/main/java/com/example/medicalaiguidance/screen/VoiceInput2Screen.kt
```

## Backend Handoff Notes

To connect the real model gateway:

1. Start the teammate/model gateway and confirm:

   ```text
   {gateway_url}/health
   ```

2. Update backend `.env`:

   ```env
   VOICE_ENABLED=true
   VOICE_GATEWAY_URL=http://localhost:8000
   VOICE_GATEWAY_KEY=actual-key
   VOICE_GATEWAY_IS_NGROK=false
   ```

   If using ngrok:

   ```env
   VOICE_GATEWAY_URL=https://xxxx.ngrok-free.dev
   VOICE_GATEWAY_IS_NGROK=true
   ```

3. Verify:

   ```text
   http://127.0.0.1:8080/voice/health
   ```

4. Test the Android app:

   - `國語` playback should call `chinese_tts`.
   - `台語` playback should call `taiwanese_tts`.
   - `台語` microphone upload should call `taiwanese_asr`.

Do not commit real `.env` files or API keys.
