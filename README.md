# Android Medical AI Guidance

智慧醫療導引系統，包含 Android Jetpack Compose 前端與 FastAPI 後端。

目前分支已將前後端整合在同一個 repository：

```text
.
├── app/                         # Android 前端
├── android_medical_backend/     # FastAPI 後端
├── gradle/
├── build.gradle.kts
├── settings.gradle.kts
└── README.md
```

## 功能

- 使用者可在 `ChatScreen` 輸入症狀並送出問診請求。
- 前端會呼叫後端 `/chat`，由後端串接 Gemini API 與規則邏輯產生回覆。
- AI 回覆會提示是否需要補充資訊、是否確認推薦科別與醫師。
- 支援歷史紀錄保存。
- 首頁會顯示最新兩筆近期對話。
- 歷史紀錄頁可刪除紀錄。
- 從歷史紀錄點選對話會回到 `ChatScreen` 並顯示該次對話。
- 按「新增問診」會開啟一個全新的空白對話。
- 支援醫師資料、科別資料與可看診時段的模擬資料。

## 前端技術

- Kotlin
- Jetpack Compose
- Android Navigation Compose
- ViewModel
- `HttpURLConnection` 呼叫後端 API

主要畫面：

```text
HomeScreen
ChatScreen
HistoryScreen
DoctorSelectionScreen
ConfirmNeedScreen
```

主要檔案：

```text
app/src/main/java/com/example/medicalaiguidance/screen/ChatScreen.kt
app/src/main/java/com/example/medicalaiguidance/viewmodel/ChatViewModel.kt
app/src/main/java/com/example/medicalaiguidance/network/MedicalApiClient.kt
app/src/main/java/com/example/medicalaiguidance/network/MedicalDtos.kt
app/src/main/java/com/example/medicalaiguidance/repository/MedicalRepository.kt
app/src/main/java/com/example/medicalaiguidance/navigation/NavGraph.kt
```

## 後端技術

- Python
- FastAPI
- Uvicorn
- Gemini API
- Rule-based triage fallback
- Mock doctor schedule fallback

後端資料夾：

```text
android_medical_backend/
```

主要後端檔案：

```text
android_medical_backend/app/main.py
android_medical_backend/app/routes/chat.py
android_medical_backend/app/routes/recommend.py
android_medical_backend/app/routes/generate_script.py
android_medical_backend/app/services/ai_service.py
android_medical_backend/app/services/rule_engine.py
android_medical_backend/app/services/case_store.py
android_medical_backend/data/doctor.json
```

## API

前端目前使用的後端網址：

```text
https://android-medical-myself.onrender.com
```

設定位置：

```text
app/src/main/java/com/example/medicalaiguidance/network/MedicalApiClient.kt
```

目前串接的 API：

```text
POST /chat
POST /recommend
POST /generate_script
```

Swagger 文件：

```text
https://android-medical-myself.onrender.com/docs
```

## 啟動後端

進入後端資料夾：

```powershell
cd android_medical_backend
```

建立虛擬環境：

```powershell
python -m venv .venv
```

啟動虛擬環境：

```powershell
.\.venv\Scripts\Activate.ps1
```

安裝套件：

```powershell
pip install -r requirements.txt
```

建立 `.env`，填入自己的環境變數：

```text
GOOGLE_API_KEY=你的 Gemini API Key
DB_PASSWORD=你的資料庫密碼
DEPLOY_MODE=render_free
DISABLE_LOCAL_EMBEDDING=true
```

啟動後端：

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

本機 Swagger：

```text
http://localhost:8000/docs
```

## 讓手機連本機後端

手機與電腦需要連到同一個 Wi-Fi。

先查電腦 IP：

```powershell
ipconfig
```

找到 Wi-Fi 的 IPv4，例如：

```text
192.168.1.23
```

接著將前端 API base URL 改成：

```kotlin
const val DEFAULT_BASE_URL = "http://192.168.1.23:8000"
```

修改位置：

```text
app/src/main/java/com/example/medicalaiguidance/network/MedicalApiClient.kt
```

後端啟動時必須使用：

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

如果只用 `127.0.0.1` 或 `localhost`，手機會連到手機自己，不會連到電腦後端。

## 建置前端 APK

回到專案根目錄：

```powershell
cd ..
```

建置 debug APK：

```powershell
.\gradlew.bat :app:assembleDebug
```

APK 位置：

```text
app/build/outputs/apk/debug/app-debug.apk
```

安裝到手機：

```powershell
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

## Render 部署

目前 Render 後端網址：

```text
https://android-medical-myself.onrender.com
```

Render 需要設定環境變數：

```text
GOOGLE_API_KEY
DB_PASSWORD
DEPLOY_MODE=render_free
DISABLE_LOCAL_EMBEDDING=true
```

Render start command：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Render free plan 可能會 cold start，第一次呼叫 API 會比較慢。

## 測試

前端建置測試：

```powershell
.\gradlew.bat :app:assembleDebug
```

後端測試：

```powershell
cd android_medical_backend
.\.venv\Scripts\python.exe -m unittest tests.test_backend_flow
```

後端語法檢查：

```powershell
.\.venv\Scripts\python.exe -m compileall app main.py
```

## 注意事項

- `.env` 不要上傳到 GitHub。
- `.venv` 不要上傳到 GitHub。
- `GOOGLE_API_KEY` 不要寫死在前端或 commit 到 repository。
- 手機測試本機後端時，前端必須使用電腦的 Wi-Fi IPv4。
- 若使用 Render 後端，前端可維持 `https://android-medical-myself.onrender.com`。
- AI 回覆時間太長時，常見原因是 Render cold start 或 Gemini API 回應較慢。
