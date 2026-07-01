# Android Medical AI Guidance

本專案包含 Android Jetpack Compose 前端與 FastAPI 後端，功能包含 AI 問診、科別/醫師推薦、掛號腳本產生，以及目前正在整合的語音功能。

這個分支是「語音整合交接分支」，目標是讓後端同學可以清楚知道目前已完成什麼、如何在本機跑起來、以及後續要怎麼換成真正的語音模型 gateway。

## 專案結構

```text
.
app/                         Android App
android_medical_backend/     FastAPI 後端
gradle/                      Gradle 設定
build.gradle.kts
settings.gradle.kts
README.md
```

## 目前語音整合狀態

### ChatScreen 語言模式

`國語` 模式：

- 麥克風維持 Android 內建語音辨識，也就是 `RecognizerIntent`。
- 使用者說話後會先由手機系統轉文字，再送原本的 `/chat`。
- AI 訊息按「播放」時，前端會呼叫後端 `/voice/tts`。
- 後端會用 `lang = "chinese"` 轉給 gateway。
- gateway 收到的 `service_type` 是 `chinese_tts`。

`台語` 模式：

- 麥克風會切換成 App 自己錄音。
- 第一次點麥克風：開始錄音。
- 第二次點麥克風：停止錄音並上傳 WAV。
- 上傳 endpoint 是 `/voice/chat`。
- 前端會帶 `lang = "taiwanese"`。
- 後端會把音檔轉給 gateway 的 `taiwanese_asr`。
- AI 訊息按「播放」時，前端會呼叫 `/voice/tts` 並帶 `lang = "taiwanese"`。
- 後端會轉給 gateway 的 `taiwanese_tts`。

## 重要限制

真正的語音模型 gateway 不在這個 repo 裡。

目前 repo 裡有一個本機測試用的相容 gateway：

```text
android_medical_backend/local_voice_gateway.py
android_medical_backend/synthesize_sapi.ps1
```

它提供和正式 gateway 類似的介面：

```text
GET  /health
POST /api/process
```

這個本機 gateway 的用途是讓前端、後端、TTS 播放流程先完整跑通。

目前本機 gateway 的狀態：

- `chinese_tts`：可產生可播放 WAV，但來源是 Windows 內建語音。
- `taiwanese_tts`：可產生可播放 WAV，但也是 Windows 內建語音 fallback，不是真正台語模型。
- `chinese_asr`：demo placeholder，固定回傳文字。
- `taiwanese_asr`：demo placeholder，固定回傳文字。

也就是說，目前可以驗證「路徑有打通」，但不是最終模型效果。後續拿到組員或學校電腦上的正式 gateway 後，只要替換 `VOICE_GATEWAY_URL` 即可。

## 後端 API

目前後端提供：

```text
POST /chat
POST /recommend
POST /generate_script
POST /voice/chat
POST /voice/tts
GET  /voice/health
```

### `/voice/chat`

用途：語音問診。前端上傳音檔，後端呼叫 gateway ASR，再走原本 `/chat` 問診邏輯，最後可再呼叫 gateway TTS。

前端會用 multipart form-data：

```text
file       WAV 音檔
case_id    可選，用來延續同一個問診 case
lang       chinese 或 taiwanese
confirmed  true 或 false
```

後端會依 `lang` 對應：

```text
chinese    -> chinese_asr / chinese_tts
taiwanese  -> taiwanese_asr / taiwanese_tts
```

### `/voice/tts`

用途：單純把 AI 訊息文字轉成語音。

Request JSON：

```json
{
  "text": "您好，這是語音測試",
  "lang": "chinese",
  "speed": 1.0
}
```

Response JSON：

```json
{
  "audio_base64": "...",
  "audio_format": "wav",
  "tts_failed": false,
  "error": null
}
```

### `/voice/health`

用途：確認後端是否有啟用語音，以及後端是否連得到 gateway。

測試網址：

```text
http://127.0.0.1:8080/voice/health
```

## Gateway 合約

後端會呼叫：

```text
POST {VOICE_GATEWAY_URL}/api/process
```

Header：

```text
X-API-Key: {VOICE_GATEWAY_KEY}
```

目前後端支援的 gateway service type：

```text
chinese_asr
taiwanese_asr
chinese_tts
taiwanese_tts
```

## 本機測試啟動流程

本機測試建議開兩個 terminal：

1. terminal A：啟動 gateway
2. terminal B：啟動 FastAPI 後端

### 1. 啟動本機相容 gateway

```powershell
cd android_medical_backend
python -m uvicorn local_voice_gateway:app --host 0.0.0.0 --port 8000
```

確認 gateway：

```text
http://127.0.0.1:8000/health
```

### 2. 設定後端 `.env`

可以複製：

```text
android_medical_backend/.env.example
```

成為：

```text
android_medical_backend/.env
```

本機測試內容：

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

注意：不要把真正的 `.env`、API key、DB password commit 到 GitHub。

### 3. 安裝後端套件

```powershell
cd android_medical_backend
python -m pip install -r requirements.txt
```

### 4. 啟動後端

後端建議跑 `8080`，因為 `8000` 留給 gateway。

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

確認後端：

```text
http://127.0.0.1:8080/docs
http://127.0.0.1:8080/voice/health
```

如果 `/voice/health` 正常，會看到類似：

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

## Android 本機測試

前端目前本機後端 base URL 設在：

```text
app/src/main/java/com/example/medicalaiguidance/network/MedicalApiClient.kt
```

目前值：

```kotlin
const val DEFAULT_BASE_URL = "http://192.168.50.63:8080"
```

如果換電腦或換 Wi-Fi，需要改成該電腦的 Wi-Fi IPv4：

```powershell
ipconfig
```

找 Wi-Fi 的 IPv4，例如：

```text
192.168.x.x
```

再改成：

```kotlin
const val DEFAULT_BASE_URL = "http://192.168.x.x:8080"
```

手機和電腦要在同一個 Wi-Fi。

## Android Build

```powershell
.\gradlew.bat assembleDebug
```

APK 位置：

```text
app/build/outputs/apk/debug/app-debug.apk
```

## 重要前端檔案

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

## 重要後端檔案

```text
android_medical_backend/app/main.py
android_medical_backend/app/routes/voice.py
android_medical_backend/app/services/voice_client.py
android_medical_backend/app/schemas.py
android_medical_backend/app/config.py
android_medical_backend/local_voice_gateway.py
android_medical_backend/synthesize_sapi.ps1
android_medical_backend/.env.example
```

## 已清掉的舊流程

以下檔案未被 `NavGraph` 或目前流程引用，已刪除：

```text
app/src/main/java/com/example/medicalaiguidance/state/TriageFlowController.kt
app/src/main/java/com/example/medicalaiguidance/screen/VoiceInput1Screen.kt
app/src/main/java/com/example/medicalaiguidance/screen/VoiceInput2Screen.kt
```

## 後端接手重點

後端同學若要接真正模型 gateway，請照下面做：

1. 啟動真正 gateway。

2. 確認 gateway health：

   ```text
   {gateway_url}/health
   ```

3. 修改 `android_medical_backend/.env`：

   ```env
   VOICE_ENABLED=true
   VOICE_GATEWAY_URL=http://localhost:8000
   VOICE_GATEWAY_KEY=actual-key
   VOICE_GATEWAY_IS_NGROK=false
   ```

   如果 gateway 是 ngrok：

   ```env
   VOICE_GATEWAY_URL=https://xxxx.ngrok-free.dev
   VOICE_GATEWAY_IS_NGROK=true
   ```

4. 重啟後端。

5. 確認：

   ```text
   http://127.0.0.1:8080/voice/health
   ```

6. 測 App：

   - 國語訊息播放應該呼叫 `chinese_tts`。
   - 台語訊息播放應該呼叫 `taiwanese_tts`。
   - 台語麥克風錄音應該呼叫 `taiwanese_asr`。

## 常見問題

### `/docs` 可以開，但播放失敗

代表 App 到後端有通，但後端到 gateway 可能沒通。

請檢查：

```text
http://127.0.0.1:8080/voice/health
http://127.0.0.1:8000/health
```

### `/voice/health` 顯示 gateway unreachable

代表 `VOICE_GATEWAY_URL` 指向的服務沒有啟動，或 port 不對。

本機測試時，請確認 gateway 跑在：

```text
http://localhost:8000
```

後端跑在：

```text
http://localhost:8080
```

### 台語 ASR 回固定文字

這是目前本機相容 gateway 的限制。它只是 demo placeholder，不是真正台語辨識。

要真正辨識台語，需要接上組員的模型 gateway。

### 台語 TTS 聽起來不像台語

目前本機相容 gateway 的 `taiwanese_tts` 是 Windows 內建語音 fallback，不是真正台語模型。

要真正台語聲音，需要接上組員的模型 gateway。
