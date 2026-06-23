# Backend Render 部署指南

更新日期：2026-06-01

本文件針對 `android_medical_backend`。Render Free 必須使用 lightweight mode，避免 OOM。

## 1. 啟動點

FastAPI app：

```text
app.main:app
```

Start command：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

主流程不變：

```text
/chat -> /chat confirmed=true -> /recommend -> /generate_script
```

## 2. Render Free Lightweight Mode

設定：

```text
DEPLOY_MODE=render_free
DISABLE_LOCAL_EMBEDDING=true
```

作用：

- 不載入 `HuggingFaceEmbedding`。
- 不安裝 `sentence-transformers`、`torch`、`transformers`。
- 不初始化本機 RAG index。
- Gemini 使用 lazy initialize。
- Gemini 失敗時 fallback rule-based。
- DB 失敗時 `/recommend` fallback mock schedule。

## 3. requirements

Render Free：

```bash
pip install -r requirements.txt
```

本機完整 AI / RAG：

```bash
pip install -r requirements-ai.txt
```

開發測試：

```bash
pip install -r requirements-dev.txt
```

## 4. Render 設定

Root Directory：

```text
android_medical_backend
```

Build Command：

```bash
pip install -r requirements.txt
```

Start Command：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 5. Environment Variables

必要：

```text
DEPLOY_MODE=render_free
DISABLE_LOCAL_EMBEDDING=true
GOOGLE_API_KEY=<Gemini key>
DB_PASSWORD=<Azure SQL password>
```

建議：

```text
PYTHON_VERSION=3.11.9
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=medichain-server.database.windows.net
DB_NAME=MediChainDB
DB_USER=medichain_admin
LLM_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=BAAI/bge-m3
```

## 6. 驗證

Render URL：

```text
https://android-medical-myself.onrender.com
```

Swagger：

```text
https://android-medical-myself.onrender.com/docs
```

測 `/chat`：

```bash
curl -X POST "https://android-medical-myself.onrender.com/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"我肚子痛，今天早上開始，沒有胸痛也沒有呼吸困難，明天上午可以看診\"}"
```

成功條件：

- HTTP 200。
- response 有 `case_id`。
- response 有 `conversation_state`。

## 7. Android BASE_URL

本次 backend 部署不修改 Android。

正式連 Render 時，改：

```text
android_medical_frontend/app/src/main/java/com/example/medicalaiguidance/data/MedicalApiClient.kt
```

設定：

```kotlin
const val DEFAULT_BASE_URL = "https://android-medical-myself.onrender.com"
```

## 8. 已知限制

- Render Free 有 cold start。
- Render native Python runtime 可能缺 SQL Server ODBC driver。
- Azure SQL 不可用時會 fallback mock schedule。
- `case_store.py` 是 in-memory，Render restart 後舊 case state 會遺失。
