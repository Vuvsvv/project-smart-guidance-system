# Android Medical Backend

更新日期：2026-06-01

FastAPI 後端，提供 Android 掛號導引主流程。

## 1. 後端用途

後端負責：

- 收集症狀與看診偏好。
- 執行 semantic normalization 與 rule-based triage。
- 控制 confirmation workflow。
- 推薦科別、醫師與時段。
- 產生 Android 導引 steps。

固定主流程：

```text
/chat -> /chat confirmed=true -> /recommend -> /generate_script
```

## 2. 本機啟動

```powershell
cd C:\Users\10650\Desktop\android_medical\android_medical_backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

或：

```powershell
.\venv\Scripts\python.exe main.py
```

Swagger：

```text
http://localhost:8000/docs
```

## 3. 測試

```powershell
.\venv\Scripts\python.exe -m compileall app main.py
.\venv\Scripts\python.exe -m unittest tests.test_backend_flow
```

目前測試涵蓋：

- `/chat`
- `/chat confirmed=true`
- `/recommend`
- `/generate_script`
- red flag anti-loop
- availability anti-loop
- DB/mock fallback
- AI unavailable fallback

## 4. API 主流程

1. `POST /chat`
   - 建立或更新 `TriageCase`。
   - 回傳 `needMoreInfo=true` 時，前端繼續顯示追問。
   - 資料足夠時進入 `waiting_confirmation`。

2. `POST /chat` with `confirmed=true`
   - 使用者確認分診結果。
   - stage 進入 `recommending`。

3. `POST /recommend`
   - 只接受已完成且已 confirmed 的 case。
   - 產生 `specialty_first` 與 `time_first`。

4. `POST /generate_script`
   - 使用 `case_id + recommendation_id`。
   - 回傳 Accessibility-oriented steps。

完整欄位請看根目錄 `API_SPEC.md`。

## 5. Semantic Normalization 摘要

相關檔案：

- `app/services/semantic_normalizer.py`
- `app/services/confidence_scoring.py`
- `app/services/clarification_engine.py`
- `app/services/rule_engine.py`

責任：

- 將自然語句轉為結構化欄位。
- 判斷欄位信心分數。
- 避免重複追問紅旗與看診時間。
- 決定下一題與 conversation stage。

## 6. AI Adapter 責任邊界

檔案：

```text
app/services/rag_triage_adapter.py
app/services/ai_service.py
```

AI 可以：

- 補強 symptom extraction。
- 協助科別判斷。
- 使用 Gemini 做 semantic extraction。

AI 不可以：

- 破壞 API contract。
- 繞過 confirmation gate。
- 覆蓋 deterministic state machine 的正式流程。

沒有 `GOOGLE_API_KEY` 或 AI 失敗時，後端必須 fallback rule-based。

## 7. Render Deployment 摘要

正式 Render：

```text
https://android-medical-myself.onrender.com
```

Render Free 使用 lightweight mode：

```text
DEPLOY_MODE=render_free
DISABLE_LOCAL_EMBEDDING=true
```

Render build：

```bash
pip install -r requirements.txt
```

Render start：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

完整部署看：

```text
DEPLOY_RENDER_GUIDE.md
../DEPLOY_RENDER_GUIDE.md
```

## 8. 環境變數

必要：

```text
GOOGLE_API_KEY
DB_PASSWORD
DEPLOY_MODE=render_free
DISABLE_LOCAL_EMBEDDING=true
```

可選：

```text
DB_DRIVER
DB_SERVER
DB_NAME
DB_USER
LLM_MODEL
EMBEDDING_MODEL
```

## 9. DB / Mock Fallback

DB：

- Azure SQL
- `pyodbc`
- SQL Server ODBC driver

Fallback：

- `data/mock_schedule.json`

Render 上 ODBC driver 不足時，`/recommend` 會 fallback mock schedule。這是目前設計的一部分。

## 10. 目前限制

- `case_store.py` 是 in-memory，server restart 後 case state 會遺失。
- Render Free cold start 可能造成第一次 request 慢。
- Azure SQL driver 在 Render Free 可能不可用。
- `script_service.py` 產生 steps，但 Android Accessibility Service 尚未正式執行。
- RAG / HuggingFace embedding prototype 保留在 `android_medical_ai`，不部署到 Render Free。

## 11. 後端下一步

1. 將 `case_store.py` 換成 SQLite / Redis / DB-backed store。
2. 正式解決 Azure SQL ODBC driver。
3. 增加 API latency log。
4. 增加 AI extraction observability。
5. 補 production health check。
