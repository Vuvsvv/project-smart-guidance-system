# Android Medical Frontend

更新日期：2026-06-01

Android Jetpack Compose 前端，負責讓使用者輸入症狀、確認分診、選擇推薦掛號方案，並顯示後端產生的導引 steps。

## 1. 前端用途

前端負責：

- 顯示入口頁。
- 在 `HelpScreen` 完成後端主流程。
- 呼叫 FastAPI 後端。
- 顯示追問、分診結果、推薦列表、導引 steps。

## 2. 主入口流程

```text
MainActivity
-> NavGraph
-> HomeScreen
-> HelpScreen
```

目前主流程集中在 `HelpScreen`，legacy voice screens 不在主線流程。

## 3. HelpScreen 現況

已支援：

- 呼叫 `POST /chat`。
- 顯示 `needMoreInfo=true` 的追問。
- 顯示 `waiting_confirmation` 確認狀態。
- 呼叫 `POST /chat` with `confirmed=true`。
- 呼叫 `POST /recommend`。
- 呼叫 `POST /generate_script`。
- 顯示 script steps。

## 4. API Base URL 設定位置

檔案：

```text
app/src/main/java/com/example/medicalaiguidance/data/MedicalApiClient.kt
```

目前常數：

```kotlin
const val DEFAULT_BASE_URL = "https://android-medical-myself.onrender.com"
```

如需本機開發，可暫時改成本機測試位址；提交或交付前應切回：

```kotlin
const val DEFAULT_BASE_URL = "https://android-medical-myself.onrender.com"
```

## 5. Render 後端 URL

```text
https://android-medical-myself.onrender.com
```

Swagger：

```text
https://android-medical-myself.onrender.com/docs
```

## 6. Build

```powershell
cd C:\Users\10650\Desktop\android_medical\android_medical_frontend
.\gradlew.bat :app:assembleDebug
```

## 7. 安裝手機測試

產物通常在：

```text
app/build/outputs/apk/debug/app-debug.apk
```

可用 Android Studio 安裝，或使用 adb：

```powershell
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

## 8. 目前已接 API

檔案：

- `data/MedicalApiClient.kt`
- `data/MedicalDtos.kt`
- `state/TriageFlowController.kt`

API：

- `/chat`
- `/recommend`
- `/generate_script`

## 9. 尚未完成

- Accessibility Service 正式執行後端 steps。
- SpeechRecognizer / 中文語音 / 台語語音接入。
- lifecycle-aware ViewModel。
- history / profile / auth API。
- 實機完整流程測試。

## 10. 注意事項

- 不要修改 API contract 時只改前端，必須同步 `API_SPEC.md` 與 backend schema。
- 不要繞過 `/chat confirmed=true`。
- Render Free cold start 時，第一次 request 可能較慢。
