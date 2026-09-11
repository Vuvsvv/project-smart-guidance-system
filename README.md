# AI 模型服務網關

統一管理多個 AI 模型的 API 網關。後端只需呼叫一個端點，透過 `service_type` 參數決定使用哪個模型。

## 架構

```
                          ┌──────────────────────┐
                          │  API Gateway (:8000)  │
     後端 ── POST ──────▶ │  依 service_type 路由  │
     service_type=xxx     └──┬─────────┬─────────┬┘
                             │         │         │
          ┌──────────────────┘         │         └──────────────────┐
          ▼                            ▼                            ▼
 ┌──────────────────┐  ┌─────────────────────┐  ┌──────────────────┐
 │ 台語 ASR (:8001) │  │ 台語 TTS (:8003)    │  │ 中文 TTS (:8004) │
 │ Breeze-ASR-26    │  │ 字典/Gemini +       │  │ BreezyVoice      │
 │                  │  │ GPT-SoVITS          │  │                  │
 │ 台語語音→中文字  │  │ 中文字→台語語音     │  │ 中文字→國語語音  │
 └──────────────────┘  └──────────┬──────────┘  └──────────────────┘
                                  │ HTTP
                                  ▼
                     宿主機 GPT-SoVITS api_v2 (:9880)
```

上面這四個方框（網關 + 三個服務）**可以整組用本機跑，也可以整組用 Docker 跑** ——
`./start_all.sh` 走本機，`docker compose up -d` 走 Docker，選一種即可。

最底下的 **GPT-SoVITS 一律留在宿主機**（吃 GPU、要你微調的權重），兩種方式都一樣。

## 服務總覽

| service_type | 輸入 | 輸出 | 模型 | Port |
|---|---|---|---|---|
| `taiwanese_asr` | 台語音訊 | 中文字 | MediaTek-Research/Breeze-ASR-26 | 8001 |
| `taiwanese_tts` | 中文字 | 台語語音 + 台語漢字 | 本地字典／Gemini + GPT-SoVITS (F1 微調) | 8003 |
| `chinese_tts` | 中文字 | 台灣國語語音 | MediaTek-Research/BreezyVoice-300M | 8004 |

> **v4.0.0 起**，台語 TTS 的底層已從舊的 VITS 聲學模型換成 **GPT-SoVITS**。
> 這個服務本身只是一個 HTTP client（不載入任何模型、requirements 裡沒有 torch），
> 所以已經可以直接容器化；真正吃 GPU 的 GPT-SoVITS `api_v2` 留在宿主機跑。

> **中文 ASR 已移除。** 前端的國語辨識改用 Android 系統內建的語音輸入，
> 延遲遠低於自架 Whisper，且不佔用顯示記憶體。台語辨識沒有堪用的現成方案，
> 因此保留自建服務 —— 資源集中在真正需要突破的地方。

## 快速開始

先準備 `.env`（兩種方式都需要）：

```bash
cp .env.example .env
nano .env   # 填入 GEMINI_API_KEY 和 API_KEY
```

然後**選一種**啟動方式。

### 方式 A：本機跑（WSL / conda）

不需要 Docker，GPT-SoVITS 綁 loopback 就好，也不用設防火牆。

```bash
# 終端機 1 —— GPT-SoVITS（吃 GPU）
conda activate GPTSoVits
cd ~/GPT-SoVITS-clean
python api_v2.py -c GPT_SoVITS/configs/tts_infer.yaml -a 127.0.0.1 -p 9880

# 終端機 2 —— 網關 + 三個服務
conda activate breezy
cd /home/tku/ai-model-gateway_bigvgan_fixed/ai-model-gateway_bigvgan
./start_all.sh
```

`start_all.sh` 會依序起 8001 → 8003 → 8004 → 8000，
並且**等每個服務的 `/` 真的回 200 才往下走**（模型載入要幾分鐘是正常的）。
按 `Ctrl+C` 會一起關掉全部。

### 方式 B：Docker

GPT-SoVITS 必須改綁 `0.0.0.0`，因為對容器來說宿主機算「外部」，
綁 `127.0.0.1` 的話 `host.docker.internal` 連不進來。
**改了就一定要用防火牆擋住 9880**（見下方「網路暴露面」）。

```bash
# 終端機 1 —— GPT-SoVITS
conda activate GPTSoVits
cd ~/GPT-SoVITS-clean
python api_v2.py -c GPT_SoVITS/configs/tts_infer.yaml -a 0.0.0.0 -p 9880

# 只需做一次
sudo ufw deny 9880/tcp

# 終端機 2
sudo docker compose up -d
```

### 確認

```bash
curl http://localhost:8000/health     # 三個服務都要是 healthy
```

API 文件：http://localhost:8000/docs

## 後端整合

後端只需要這些程式碼，同一個端點切換三種服務：

```python
import os, requests, base64, json

GATEWAY = "http://localhost:8000"
HEADERS = {"X-API-Key": os.environ["API_KEY"]}   # 缺這個會 401

# ── 台語語音 → 中文字（Breeze-ASR-26）──
with open("taiwanese.wav", "rb") as f:
    r = requests.post(f"{GATEWAY}/api/process",
        headers=HEADERS,
        files={"file": f},
        data={"service_type": "taiwanese_asr"})
print(r.json()["data"]["text"])

# ── 中文字 → 台語語音（Gemini + GPT-SoVITS）──
r = requests.post(f"{GATEWAY}/api/process",
    headers=HEADERS,
    data={
        "service_type": "taiwanese_tts",
        "text_input": "頭痛要看醫生",
        "extra_params": json.dumps({"speed": 0.85})
    })
result = r.json()["data"]
print(result["taigi_hanji"])                  # 台語漢字（中間產物）
# 預設輸出 m4a（AAC）；副檔名請依 result["audio_format"] 決定，不要寫死
audio = base64.b64decode(result["audio_base64"])
with open(f"taiwanese.{result['audio_format']}", "wb") as f:
    f.write(audio)

# ── 中文字 → 台灣國語語音（BreezyVoice）──
r = requests.post(f"{GATEWAY}/api/process",
    headers=HEADERS,
    data={
        "service_type": "chinese_tts",
        "text_input": "你好，今天天氣真好"
    })
result = r.json()["data"]
audio = base64.b64decode(result["audio_base64"])
with open(f"mandarin.{result['audio_format']}", "wb") as f:
    f.write(audio)
```

### 回應格式與狀態碼

body 一律是同一個信封 `{success, service_type, timestamp, data, error, processing_time_ms}`，
失敗時 **HTTP status code 也會帶語意**，呼叫端可以直接用來決定要不要重試：

| status | 意思 | 該不該重試 |
|---|---|---|
| 200 | 成功 | — |
| 400 | 輸入有問題（缺 text_input、檔案格式不對…） | 否 |
| 401 / 403 | API Key 無效／權限不足 | 否 |
| 404 | 未知的 service_type | 否 |
| 413 | 檔案超過大小上限 | 否 |
| 429 | 超過速率限制（看 `Retry-After`） | 稍後再試 |
| 503 | 該服務未啟用 | 否 |
| 502 / 504 | 下游服務異常／逾時 | 可以 |

判斷失敗請看 **status code**，不要只看 body 的 `success`：
FastAPI 的參數驗證錯誤（422）回的是 `{"detail": ...}`，沒有 `success` 欄位。

```python
if resp.status_code != 200:
    body = resp.json()
    raise RuntimeError(body.get("error") or body.get("detail") or body)
```

### 已棄用欄位

`taiwanese_tts` 回應中的 **`tailo_romanization` 已 deprecated**：
自 v4.0.0 起它裝的是「台語漢字」而不是台羅拼音，名稱與內容不符，
只為了相容舊呼叫端而保留，預計於 **v5.0.0 移除**。
新的呼叫端請一律改用 **`taigi_hanji`**。

## 網路暴露面

**只有網關的 `:8000` 應該對外。** 8001／8003／8004 那三個微服務**沒有任何 API Key 檢查** ——
它們的設計前提是「只有網關會來找」，所以對外開放等於讓人繞過認證直接呼叫模型，
其中 `:8003` 背後接的是 Gemini，會直接花掉你的額度。

| Port | 是什麼 | 對外 |
|---|---|---|
| 8000 | API 網關（有 API Key 認證） | ✅ 開放 |
| 8001, 8003, 8004 | 三個微服務（**無認證**） | ❌ 只綁 `127.0.0.1` |
| 9880 | GPT-SoVITS api_v2（**無認證**） | ❌ 防火牆擋掉 |

- **Docker**：`docker-compose.yml` 已把三個微服務綁在 `127.0.0.1`。
  要除錯就在宿主機上 `curl http://127.0.0.1:8003/`，或開 SSH tunnel。
- **VPS**：`deploy.sh` 產生的 systemd unit 全部綁 `127.0.0.1`，並額外用 ufw 明確擋掉這些 port。
- **GPT-SoVITS**：因為容器要連得到，必須用 `-a 0.0.0.0` 啟動 ——
  所以**一定要自己用防火牆擋住 9880**，否則等於把模型直接放到網路上：

  ```bash
  sudo ufw deny 9880/tcp        # Linux / WSL
  ```

  只在本機（非 Docker）跑台語 TTS 的話，`-a 127.0.0.1` 就夠，不需要這條規則。

## API Key 與權限

- `API_KEY=<key>` — 單一金鑰，預設具備 `*`（含 admin）權限。
- `API_KEYS=<key>:<名稱>[:<權限>]` — 多組金鑰，逗號分隔。
  第三段省略時只有 `process` 權限，**打不了 `POST /api/reload-config`**。
  例：`API_KEYS=sk-a:後端A,sk-b:後端B,sk-ops:維運:*`
- 速率限制以「金鑰的 hash」分桶，同名的兩把 key 不會互相吃配額；
  未認證請求以來源 IP 分桶（在 Nginx 後面時要設 `TRUSTED_PROXY_HOPS=1`，
  否則所有匿名請求都會被算成同一個 `127.0.0.1`）。

## 台語 TTS 與 GPT-SoVITS 怎麼分工

```
Docker 容器（台語 TTS :8003）              宿主機
──────────────────────────────────       ──────────────────────
中文字 → 快取／字典／Gemini → 台語漢字
        → 詞彙替換 → 拆句
        → POST host.docker.internal:9880/tts  ─▶  GPT-SoVITS api_v2
                                                   （GPU、F1 微調權重）
        ◀── WAV ────────────────────────────────
        → 串接 → base64 WAV / M4A
```

### 中文轉台語漢字的三層機制

Gemini 呼叫一次約 3.5 秒，佔掉整個請求七成以上的時間，因此在它前面加了兩層：

| 層 | 命中條件 | 耗時 |
|---|---|---|
| 快取 | 同一句先前轉換過 | ~0 秒 |
| **本地字典** | 覆蓋率達門檻 | ~0 秒 |
| Gemini | 前兩層都沒中（結果會存進快取） | ~3.5 秒 |

字典採**最長匹配**掃描，覆蓋率＝命中漢字數 ÷ 全句漢字數（標點與數字不計）。
兩道門檻：覆蓋率 `≥0.9` 直接採用；`≥0.75` 且未命中的**都是零星單字**時也採用 ——
差一兩個字就退回 Gemini 要付數秒代價，而落單的字多半中台同形，保留原樣的風險小得多。

專科名以「值＝鍵」的形式收錄：輸出保持中文（讓長輩對照醫院指示牌），
但算作已知詞，不會拉低覆蓋率而誤觸 Gemini。

**字典會自己告訴你該補什麼** —— 覆蓋率不足時 log 會列出未收錄詞：

```
├ 字典覆蓋率不足 78%，改用 Gemini（未收錄：神經內科）
```

補進 `data/taigi_dict.json` 存檔即生效（以 mtime 偵測變動，不必重啟）。
也可以主動查：

```bash
curl -X POST http://localhost:8003/api/convert \
  -H "Content-Type: application/json" \
  -d '{"text":"我最近常常頭暈"}'
# 回傳 dict_coverage / dict_misses / used_gemini
```

改過 prompt 或字典後，舊快取的轉換結果會與新邏輯不一致，記得清掉：

```bash
curl -X DELETE http://localhost:8003/api/cache
```

### 可獨立調整的地方

改完存檔即生效，不用重啟（compose 已把前三個掛成 volume）：

1. `services/taiwanese_tts/data/taigi_dict.json` — 中文→台語漢字轉換表
2. `services/taiwanese_tts/prompts/taigi_hanji.txt` — Gemini 轉換指令（字典沒中時才用）
3. `services/taiwanese_tts/data/word_replace.json` — 念不好的詞替換表（在轉換之後套用）
4. `.env` 的 `MAX_SEG_LEN` — 拆句長度上限（實測 80 字內不吞字，預設 70）

### 音訊輸出

兩個 TTS 預設輸出 **M4A（AAC 64kbps、22.05kHz 單聲道）**，
體積約為未壓縮 WAV 的七分之一（台語短句 148KB → 21KB），
Android `MediaPlayer` 原生支援。回應的 `audio_format` 會如實回報格式，
**呼叫端請依它決定副檔名，不要寫死 `.wav`**。

需要未壓縮輸出時（例如要把音檔餵回 ASR 驗證，`soundfile` 讀不了 AAC）：

```bash
TTS_OUTPUT_FORMAT=wav    # 兩個 TTS 皆適用
TTS_OUTPUT_SR=32000      # 台語：回到 GPT-SoVITS 原始取樣率
AAC_BITRATE=96k          # 覺得音質不夠可調高
```

### 啟動預熱

首次推論要配置顯存並初始化運算環境，實測比穩定後慢一個量級
（台語首句 17.7 秒 vs 穩定後 0.9 秒）。兩個 TTS 都會在啟動後自動送一次短句，
把這筆一次性成本挪到沒人等待的時候。設 `TTS_WARMUP=0` 可關閉。

## 新增服務

只需兩步，不改程式碼：

**步驟 1：** 在 `services_config.yaml` 加設定（欄位會用 Pydantic 驗證，打錯字會在載入時就報錯）

**步驟 2：** 啟動對應微服務

熱重載：`POST /api/reload-config`（需要 admin 權限；驗證失敗時會保留原設定）

每個服務的 `endpoint` 都可以用環境變數 `<SERVICE_TYPE>_ENDPOINT` 覆蓋，
例如 `CHINESE_TTS_ENDPOINT=http://127.0.0.1:8004`。

## 測試

不需要 GPU、也不需要下游服務真的存在：

```bash
pip install pytest respx httpx fastapi pyyaml python-multipart
pytest tests -q
```

## 專案結構

```
├── gateway.py                      # API 網關
├── security.py                     # 安全中間件（認證 / 權限 / 速率限制）
├── services_config.yaml            # 本機環境設定
├── services_config_docker.yaml     # Docker 環境設定（容器名稱）
├── services_config_vps.yaml        # 裸機 VPS 設定（deploy.sh 用，全部 127.0.0.1）
├── docker-compose.yml              # Docker 編排（網關 + 3 個服務）
├── start_all.sh                    # 一鍵啟動腳本
├── deploy.sh                       # VPS 部署腳本
├── manage.sh                       # 日常管理工具
├── test_client.py                  # 互動式手動測試 / 後端整合範例
├── tests/                          # 不需 GPU 的自動化測試
└── services/
    ├── breezy_asr/                 # service_type: taiwanese_asr  (:8001)
    ├── taiwanese_tts/              # service_type: taiwanese_tts  (:8003)
    └── breezy_tts/                 # service_type: chinese_tts    (:8004)
```

每個服務都只有一個 `main.py`，三條啟動路徑（Docker / `start_all.sh` / systemd）
指向的模組由 `tests/test_deployment.py` 驗證，不會再出現「部署的是舊版」的情況。

> 目錄名稱和 `service_type` 目前對不起來（`breezy_asr` ↔ `taiwanese_asr`、
> `breezy_tts` ↔ `chinese_tts`），這是 `deploy.sh` 曾經寫錯模組路徑的原因。
> 後續建議統一用 `service_type` 當唯一命名。

### 中文 TTS 的版本

`services/breezy_tts/main.py` 是 **4.0.0**（FP16 + 長句切割），
原本叫 `main_v2.py`；舊的 3.0.0 實作已刪除。
`services_config*.yaml` 的 `chinese_tts.version` 必須與它自報的版本一致 ——
對不上時 `tests/test_deployment.py` 會擋下來。
