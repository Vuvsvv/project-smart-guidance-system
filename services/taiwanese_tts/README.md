# 台語 TTS 服務 (v4 — GPT-SoVITS)

中文字 → 台語漢字(Gemini) → 詞彙替換 → 拆句 → GPT-SoVITS API → 語音

**port 8003，service_type 仍是 `taiwanese_tts`** — gateway 與前端完全不用改。
舊版 VITS+BigVGAN 實作已刪除，需要時請查 git 歷史。

## 啟動順序（兩層，缺一不可）

### 1. GPT-SoVITS api_v2（GPTSoVits conda 環境）

```bash
conda activate GPTSoVits
cd ~/GPT-SoVITS-clean
nohup env HF_HUB_OFFLINE=1 python api_v2.py \
  -c GPT_SoVITS/configs/tts_infer.yaml \
  -a 127.0.0.1 -p 9880 > ~/gsv_api.log 2>&1 &
# 本服務改用 Docker 跑時要改成 -a 0.0.0.0，並用防火牆擋掉 9880（GSV 沒有認證）

curl -s http://127.0.0.1:9880/docs >/dev/null && echo "GSV API OK"
```

`tts_infer.yaml` 的 `custom:` 區塊要指向 F1 模型：
```yaml
custom:
  t2s_weights_path: GPT_weights_v2/F1-e15.ckpt
  vits_weights_path: SoVITS_weights_v2/F1_e15_s11955.pth
```

### 2. 本服務

```bash
export GEMINI_API_KEY=你的key
python services/taiwanese_tts/main.py    # port 8003
```

## 環境相依的三個修正（做在 GPT-SoVITS 那邊，不在本專案內）

重裝 GPT-SoVITS 時必須重做：

1. **關閉 CUDA Graph**（Blackwell + nightly torch 會 token 錯亂／重複）
   `GPT_SoVITS/inference_webui.py` 第 170 行：
   ```python
   cuda_graph_supported = False
   ```

2. **繞過 torchcodec**（FFmpeg 8.x 不相容）
   `GPT_SoVITS/TTS_infer_pack/TTS.py` 第 772 行：
   ```python
   import soundfile as _sf
   _a, raw_sr = _sf.read(ref_audio_path, dtype="float32", always_2d=True)
   raw_audio = torch.from_numpy(_a.T)
   ```

3. **prompt_text 留空**（issue #2658，帶參考文字會嚴重吞字）
   本服務已用 `GSV_PROMPT_TEXT=""` 處理。

## 三個可調整的地方（改完存檔即生效，不用重啟）

1. `prompts/taigi_hanji.txt` — Gemini 轉換指令
2. `data/word_replace.json` — 醫療詞替換表，念成華語的詞加一筆：
   ```json
   { "批價": "納錢" }
   ```
3. 環境變數：
   ```bash
   MAX_SEG_LEN=70               # 拆句上限（實測 80 字開始吞字）
   SEG_GAP_SEC=0.25             # 段落間靜音長度
   GSV_REF_AUDIO=/path/to.wav   # 參考音（3-10 秒）
   GSV_API=http://127.0.0.1:9880
   ```

## API（與舊版相容）

### POST /api/synthesize
```json
{ "text": "你頭很痛嗎？建議去看神經內科", "speed": 1.0, "format": "wav" }
```
回傳 `audio_base64`、`taigi_hanji`、`segments`。
`tailo_romanization` 欄位保留（內容改放台語漢字），舊前端不會壞。

`skip_gemini: true` 可直接餵台語漢字，跳過 Gemini。

### POST /api/convert（新增）
只轉文字不合成，用來快速驗證 prompt：
```bash
curl -X POST http://localhost:8003/api/convert \
  -H "Content-Type: application/json" \
  -d '{"text":"你頭很痛嗎？建議去看神經內科，請先去掛號"}'
```

## 為何換掉 VITS

| | VITS + BigVGAN (v3) | GPT-SoVITS (v4) |
|---|---|---|
| 音質 | 男聲底模遷移女聲產生電音，需 noisereduce 壓制 | 乾淨，32k |
| 輸入 | 台羅拼音 | 台語漢字 |
| 專業詞 | 台羅可念任意詞 | 部分念成華語 → 替換表處理 |
| 長度 | 無限制 | 需拆句 ≤70 字 |
