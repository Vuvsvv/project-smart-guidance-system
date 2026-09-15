"""
台語文字轉語音服務 — GPT-SoVITS (F1 微調)

中文字 → 台語漢字(Gemini) → 詞彙替換 → 拆句 → GPT-SoVITS API → WAV/M4A
端口: 8003

v4.1.0 變更：預設輸出改為 M4A(AAC)，並在編碼時降採樣至 22.05kHz
  目的：降低傳輸體積（32kHz WAV 約 148KB → 22kHz AAC 約 20KB），
        縮短「合成完成」到「聽到聲音」之間的延遲。
  兩者皆可用環境變數調回原設定：
    TTS_OUTPUT_FORMAT=wav   → 回到未壓縮 WAV
    TTS_OUTPUT_SR=32000     → 回到原始取樣率
  對外 API 欄位不變，audio_format 會如實回報實際格式。

v4.0.0 變更：底層 TTS 從 VITS+BigVGAN 換成 GPT-SoVITS
  舊的 VITS+BigVGAN 實作已刪除（需要時查 git 歷史）
  對外 API（/api/synthesize、欄位名稱）完全相容，gateway 與前端不用改

架構說明：
  本服務不直接載入模型，而是呼叫已啟動的 GPT-SoVITS api_v2（預設 :9880）。
  GPT-SoVITS 需在 GPTSoVits conda 環境另外啟動：
    cd ~/GPT-SoVITS-clean
    python api_v2.py -c GPT_SoVITS/configs/tts_infer.yaml -a 127.0.0.1 -p 9880

  本服務改用 Docker 跑的時候，GSV 要改成 -a 0.0.0.0（容器連不到 loopback），
  同時務必用防火牆擋掉 9880 對外 —— GSV 沒有任何認證。

三個可獨立調整的地方（不用改本程式，改完存檔即生效）：
  1. prompts/taigi_hanji.txt   ← Gemini 轉換指令
  2. data/word_replace.json    ← 念不好的詞替換表
  3. .env 的 MAX_SEG_LEN       ← 拆句長度上限（實測 80 字內不吞字，預設 70）
"""

import asyncio
import os
import io
import time
import re
import json
import base64
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np
import soundfile as sf
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="台語文字轉語音服務", version="4.8.0")

# ══════════════════════════════════════════
# 設定（用環境變數覆蓋）

BASE_DIR = Path(__file__).parent

GSV_API = os.getenv("GSV_API", "http://127.0.0.1:9880")
GSV_REF_AUDIO = os.getenv(
    "GSV_REF_AUDIO",
    "/home/tku/bigvgan_data/wavs/F1_B_74_F1_B_74-55.wav"
)
# ⚠️ prompt_text 必須留空：GPT-SoVITS issue #2658，帶 prompt_text 會嚴重吞字
GSV_PROMPT_TEXT = os.getenv("GSV_PROMPT_TEXT", "")
# 比網關給本服務的 timeout（services_config.yaml: 300s）短一點，
# 這樣逾時的時候回的是這裡的具體錯誤，而不是網關的 504
GSV_TIMEOUT = float(os.getenv("GSV_TIMEOUT", "280"))

PROMPT_PATH = Path(os.getenv("TAIGI_PROMPT_PATH", BASE_DIR / "prompts/taigi_hanji.txt"))
REPLACE_PATH = Path(os.getenv("WORD_REPLACE_PATH", BASE_DIR / "data/word_replace.json"))

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_SEG_LEN = int(os.getenv("MAX_SEG_LEN", "70"))   # 實測 80 字內安全，留邊際
SEG_GAP_SEC = float(os.getenv("SEG_GAP_SEC", "0.25"))
SAMPLE_RATE = int(os.getenv("GSV_SAMPLE_RATE", "32000"))   # GPT-SoVITS v2 輸出

# ── 輸出格式設定（v4.1.0 新增）────────────────────────────
# 預設輸出 m4a：體積約為 WAV 的 1/7，Android MediaPlayer 原生支援。
# 語音清晰度在 22.05kHz / 64kbps 已足夠，長者聽感與 32kHz WAV 無明顯差異。
# ── 台語漢字轉換快取（v4.4.0 新增）──────────────────────
# 同一句中文轉出的台語漢字永遠相同，沒有理由每次都呼叫 Gemini。
# 實測 Gemini 往返約 3.5 秒，佔一次請求總時間的七成以上。
# 快取只存 Gemini 的原始輸出，詞彙替換仍每次重跑 —— 這樣改
# word_replace.json 依然即時生效，不會被舊快取蓋住。
# ── 本地字典轉換（v4.5.0 新增）──────────────────────────
# 醫療問診用詞範圍有限，多數句子可用查表完成，不必每次呼叫 Gemini。
# 命中率不足時才 fallback，並把 Gemini 的結果存進快取補洞。
TAIGI_DICT_ENABLED = os.getenv("TAIGI_DICT_ENABLED", "1") == "1"
TAIGI_DICT_PATH = Path(os.getenv("TAIGI_DICT_PATH", BASE_DIR / "data/taigi_dict.json"))
# 覆蓋率門檻：低於此值代表句中有太多未知詞，混合輸出會不自然，交給 Gemini。
TAIGI_DICT_MIN_COVERAGE = float(os.getenv("TAIGI_DICT_MIN_COVERAGE", "0.9"))
# 寬容門檻：覆蓋率介於兩者之間、且未命中的都是單字時，仍採用字典結果。
# 差一兩個字就退回 Gemini 要付數秒代價，而落單的字多半中台同形，
# 保留原樣的風險遠低於那幾秒等待。連續兩字以上未命中則照樣 fallback。
TAIGI_DICT_LENIENT_COVERAGE = float(os.getenv("TAIGI_DICT_LENIENT_COVERAGE", "0.75"))

TAIGI_CACHE_ENABLED = os.getenv("TAIGI_CACHE_ENABLED", "1") == "1"
TAIGI_CACHE_PATH = Path(os.getenv("TAIGI_CACHE_PATH", BASE_DIR / "data/taigi_cache.json"))
TAIGI_CACHE_MAX = int(os.getenv("TAIGI_CACHE_MAX", "2000"))

# 啟動後先向 GPT-SoVITS 送一次短句。實測首句約 17 秒、穩定後不到 1 秒，
# 差距來自模型初始化；預熱把這筆成本挪到啟動階段，展示時不會卡在第一句。
WARMUP_ENABLED = os.getenv("TTS_WARMUP", "1") == "1"
WARMUP_TEXT = os.getenv("TTS_WARMUP_TEXT", "你好")

DEFAULT_FORMAT = os.getenv("TTS_OUTPUT_FORMAT", "m4a").lower()
TARGET_SR = int(os.getenv("TTS_OUTPUT_SR", "22050"))   # 編碼時降採樣的目標
AAC_BITRATE = os.getenv("AAC_BITRATE", "64k")          # 語音用 64k 已充裕

genai_configured = False

# 轉換快取：{中文原句: 台語漢字}。dict 保有插入順序，滿了就從最舊的開始丟。
_taigi_cache: dict = {}
_cache_hits = 0
_cache_misses = 0
_dict_hits = 0          # 字典覆蓋率達標，未呼叫 Gemini
_gemini_calls = 0       # 實際呼叫 Gemini 的次數

_taigi_dict: dict = {}
_dict_lengths: list = []   # 字典中出現過的詞長，由長到短
_dict_mtime: float = 0.0   # 字典檔上次修改時間，用於自動重載

# 共用的 httpx client：每段落都重新建立等於每次都重做一次 TCP handshake
_http_client: Optional[httpx.AsyncClient] = None


# ══════════════════════════════════════════

def get_client() -> httpx.AsyncClient:
    """取得共用的 httpx client（第一次呼叫時建立）。"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(GSV_TIMEOUT),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http_client


class TTSRequest(BaseModel):
    text: str
    speed: float = 1.0
    # v4.1.0：預設值改由 TTS_OUTPUT_FORMAT 決定（預設 m4a）
    format: str = DEFAULT_FORMAT     # "wav" 或 "m4a"
    skip_gemini: bool = False        # True = text 已是台語漢字，跳過轉換


class TTSResponse(BaseModel):
    # ⚠️ deprecated：`tailo_romanization` 自 v4.0.0 起裝的是「台語漢字」而不是台羅拼音，
    #    名稱與內容不符，只為了相容舊呼叫端而保留。新的呼叫端請改用 `taigi_hanji`。
    #    預計於 v5.0.0 移除。
    success: bool
    tailo_romanization: str = ""   # deprecated，請改用 taigi_hanji
    taigi_hanji: str = ""          # Gemini 轉出的台語漢字
    original_text: str = ""
    segments: List[str] = []       # 實際拆成幾段送給模型
    audio_base64: Optional[str] = None
    audio_format: str = "wav"
    audio_duration: Optional[float] = None
    sample_rate: int = SAMPLE_RATE
    error: Optional[str] = None


# ───────────────────── 資源載入 ─────────────────────

def load_prompt() -> str:
    """每次呼叫都重讀，改 prompt 檔不用重啟服務"""
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"讀不到 prompt 檔 {PROMPT_PATH}: {e}，改用內建預設")
        return (
            "請將以下繁體中文轉換成台語漢字（漢羅台文），使用教育部推薦用字，"
            "醫院專科名保留中文，只輸出結果不要解釋：\n{text}"
        )


def load_replace_map() -> dict:
    """每次呼叫都重讀，改替換表不用重啟服務"""
    try:
        data = json.loads(REPLACE_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        logger.warning(f"讀不到替換表 {REPLACE_PATH}: {e}")
        return {}


# ───────────────────── 本地字典 ─────────────────────

def load_taigi_dict() -> None:
    """載入字典並建立長度索引。

    只試字典中實際存在的詞長，避免對不存在的長度做無謂查詢。
    以底線開頭的鍵是註解，不納入。
    """
    global _taigi_dict, _dict_lengths, _dict_mtime
    if not TAIGI_DICT_ENABLED:
        return
    try:
        raw = json.loads(TAIGI_DICT_PATH.read_text(encoding="utf-8"))
        _taigi_dict = {
            k: v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, str) and k and v
        }
        _dict_lengths = sorted({len(k) for k in _taigi_dict}, reverse=True)
        _dict_mtime = TAIGI_DICT_PATH.stat().st_mtime
        logger.info(
            f"✅ 台語字典已載入 {len(_taigi_dict)} 條"
            f"（詞長 {min(_dict_lengths) if _dict_lengths else 0}"
            f"~{max(_dict_lengths) if _dict_lengths else 0} 字）"
        )
    except FileNotFoundError:
        logger.warning(f"找不到字典 {TAIGI_DICT_PATH}，一律走 Gemini")
    except Exception as e:
        logger.warning(f"字典載入失敗，一律走 Gemini：{e}")


def reload_dict_if_changed() -> None:
    """字典檔有變動就重新載入。

    prompt 與替換表都是每次呼叫重讀，改完即時生效；字典若只在啟動時載入，
    行為就與另外兩者不一致，容易誤以為改完已生效而其實還在用舊資料。
    這裡用 mtime 比對，只在檔案真的變動時才重讀 —— 一次 stat 的成本可忽略。
    """
    global _dict_mtime
    if not TAIGI_DICT_ENABLED:
        return
    try:
        mtime = TAIGI_DICT_PATH.stat().st_mtime
    except OSError:
        return
    if mtime != _dict_mtime:
        logger.info("偵測到字典檔異動，重新載入")
        load_taigi_dict()


def _is_hanzi(ch: str) -> bool:
    """是否為需要轉換的漢字。標點、數字、英文、空白不計入覆蓋率分母。"""
    return "\u4e00" <= ch <= "\u9fff"


def dict_convert(text: str) -> Tuple[str, float, List[str]]:
    """以最長匹配掃描全句。

    Returns:
        (轉換結果, 覆蓋率, 未命中片段)

    覆蓋率 = 命中的漢字數 ÷ 全句漢字數。標點與數字不計。
    未命中片段用於擴充字典 —— 看 /api/convert 就知道該補哪些詞。
    """
    reload_dict_if_changed()
    if not _taigi_dict:
        return text, 0.0, [text]

    out: List[str] = []
    misses: List[str] = []
    matched = total = 0
    buf = ""          # 累積連續未命中的漢字，一起回報比逐字回報好讀
    i, n = 0, len(text)

    while i < n:
        hit = None
        for L in _dict_lengths:
            if i + L > n:
                continue
            seg = text[i:i + L]
            if seg in _taigi_dict:
                hit = seg
                break

        if hit:
            if buf:
                misses.append(buf)
                buf = ""
            out.append(_taigi_dict[hit])
            cnt = sum(1 for c in hit if _is_hanzi(c))
            matched += cnt
            total += cnt
            i += len(hit)
        else:
            ch = text[i]
            out.append(ch)
            if _is_hanzi(ch):
                total += 1
                buf += ch
            elif buf:
                misses.append(buf)
                buf = ""
            i += 1

    if buf:
        misses.append(buf)

    coverage = 1.0 if total == 0 else matched / total
    return "".join(out), coverage, misses


# ───────────────────── 轉換快取 ─────────────────────

def load_taigi_cache() -> None:
    """啟動時載入快取，讓服務重啟後不必重新暖機。"""
    global _taigi_cache
    if not TAIGI_CACHE_ENABLED:
        return
    try:
        data = json.loads(TAIGI_CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _taigi_cache = {
                k: v for k, v in data.items()
                if isinstance(k, str) and isinstance(v, str) and k and v
            }
            logger.info(f"✅ 台語轉換快取已載入 {len(_taigi_cache)} 筆")
    except FileNotFoundError:
        logger.info("尚無快取檔，將於首次轉換後建立")
    except Exception as e:
        # 快取壞掉不該讓服務起不來，清空重建即可
        logger.warning(f"快取檔讀取失敗，改為空快取：{e}")
        _taigi_cache = {}


def save_taigi_cache() -> None:
    """寫入快取檔。

    先寫暫存檔再 os.replace：若程序在寫入途中被中斷，
    直接寫本檔會留下半截 JSON，下次啟動整份快取都救不回來。
    """
    if not TAIGI_CACHE_ENABLED:
        return
    try:
        TAIGI_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = TAIGI_CACHE_PATH.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(_taigi_cache, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        os.replace(tmp, TAIGI_CACHE_PATH)
    except Exception as e:
        logger.warning(f"快取寫入失敗（不影響本次合成）：{e}")


def _cache_put(key: str, value: str) -> None:
    """存入快取，超過上限就淘汰最早插入的項目。"""
    _taigi_cache[key] = value
    if len(_taigi_cache) > TAIGI_CACHE_MAX:
        for old in list(_taigi_cache.keys())[: len(_taigi_cache) - TAIGI_CACHE_MAX]:
            _taigi_cache.pop(old, None)


# ───────────────────── 文字處理 ─────────────────────

async def chinese_to_taigi(text: str) -> str:
    """
    中文 → 台語漢字（Gemini，附快取）

    `generate_content()` 是同步呼叫、要跑好幾秒，直接在 async endpoint 裡呼叫
    會卡住整個 event loop（連 health check 都回不了），所以丟到 thread 執行。

    註：兩個相同請求同時進來時都會落空並各自呼叫一次 Gemini。
        加 per-key 鎖可以避免，但問診是逐輪對話、幾乎不會同時撞同一句，
        為此增加鎖的複雜度不划算。
    """
    global _cache_hits, _cache_misses, _dict_hits, _gemini_calls

    key = text.strip()
    if TAIGI_CACHE_ENABLED and key in _taigi_cache:
        _cache_hits += 1
        logger.info(f"├ 快取命中（累計 {_cache_hits} 次，省下一次 Gemini 呼叫）")
        return _taigi_cache[key]

    # 字典優先：覆蓋率達標就直接輸出，完全不碰網路
    if TAIGI_DICT_ENABLED and _taigi_dict:
        converted, coverage, misses = dict_convert(key)
        if coverage >= TAIGI_DICT_MIN_COVERAGE:
            _dict_hits += 1
            logger.info(f"├ 字典轉換（覆蓋率 {coverage:.0%}，未呼叫 Gemini）")
            return converted

        # 寬容判定：只差零星單字時不值得為此付一次 Gemini 往返
        if coverage >= TAIGI_DICT_LENIENT_COVERAGE and all(len(m) == 1 for m in misses):
            _dict_hits += 1
            logger.info(
                f"├ 字典轉換（覆蓋率 {coverage:.0%}，僅單字未收錄："
                f"{'、'.join(misses)}，仍免呼叫 Gemini）"
            )
            return converted

        logger.info(
            f"├ 字典覆蓋率不足 {coverage:.0%}，改用 Gemini"
            f"（未收錄：{'、'.join(misses[:5])}）"
        )

    _cache_misses += 1
    _gemini_calls += 1
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = load_prompt().replace("{text}", text)
    response = await asyncio.to_thread(model.generate_content, prompt)
    out = response.text.strip()
    out = out.strip("`").strip().strip("「」\"'")

    if TAIGI_CACHE_ENABLED and key and out:
        _cache_put(key, out)
        await asyncio.to_thread(save_taigi_cache)

    return out


def apply_replacements(text: str) -> str:
    """套用醫療詞替換表（修正 GPT-SoVITS 念不好的詞）"""
    for old, new in load_replace_map().items():
        if old in text:
            text = text.replace(old, new)
    return text


def split_for_tts(text: str, max_len: int = None) -> List[str]:
    """
    依標點拆句，每段不超過 max_len 字。
    GPT-SoVITS 超過約 80 字會吞字（實測），故拆段後逐段合成再串接。
    """
    max_len = max_len or MAX_SEG_LEN
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    parts = [p for p in re.split(r"(?<=[。？！；])", text) if p.strip()]
    result: List[str] = []
    buf = ""

    for p in parts:
        if len(p) > max_len:
            subs = [s for s in re.split(r"(?<=[，、])", p) if s.strip()]
            for s in subs:
                if len(buf) + len(s) <= max_len:
                    buf += s
                else:
                    if buf:
                        result.append(buf)
                    while len(s) > max_len:
                        result.append(s[:max_len])
                        s = s[max_len:]
                    buf = s
        else:
            if len(buf) + len(p) <= max_len:
                buf += p
            else:
                if buf:
                    result.append(buf)
                buf = p

    if buf:
        result.append(buf)
    return result


# ───────────────────── 語音合成 ─────────────────────

async def gsv_synthesize(segment: str, speed: float) -> Tuple[np.ndarray, int]:
    """呼叫 GPT-SoVITS api_v2 合成單一段落"""
    payload = {
        "text": segment,
        "text_lang": "zh",
        "ref_audio_path": GSV_REF_AUDIO,
        "prompt_text": GSV_PROMPT_TEXT,     # 留空，避免吞字
        "prompt_lang": "zh",
        "text_split_method": "cut0",        # 不切（我們自己拆好了）
        "speed_factor": speed if speed > 0 else 1.0,
        "media_type": "wav",
        "streaming_mode": False,
    }
    _t = time.perf_counter()
    r = await get_client().post(f"{GSV_API}/tts", json=payload, timeout=GSV_TIMEOUT)
    logger.info(f"  ├ GSV 呼叫 {time.perf_counter()-_t:.2f}s（{len(segment)} 字）")
    if r.status_code != 200:
        raise RuntimeError(f"GPT-SoVITS 回傳 {r.status_code}: {r.text[:200]}")

    wav, sr = sf.read(io.BytesIO(r.content), dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    return wav, sr


async def synthesize_all(
    segments: List[str], speed: float
) -> Tuple[np.ndarray, float, int]:
    """逐段合成後串接，段落間加短靜音（長輩聽起來有停頓較清楚）

    Returns:
        (waveform, duration_seconds, sample_rate)
    """
    pieces = []
    sr_out = SAMPLE_RATE

    for i, seg in enumerate(segments):
        logger.info(f"合成第 {i+1}/{len(segments)} 段（{len(seg)} 字）")
        wav, sr = await gsv_synthesize(seg, speed)
        sr_out = sr
        pieces.append(wav)
        if i < len(segments) - 1:
            pieces.append(np.zeros(int(sr * SEG_GAP_SEC), dtype=np.float32))

    full = np.concatenate(pieces) if pieces else np.zeros(1, dtype=np.float32)
    return full, len(full) / sr_out, sr_out


# ───────────────────── 輸出格式 ─────────────────────

def to_wav_bytes(wf: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, wf, sr, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()


def to_m4a_bytes(wf: np.ndarray, sr: int, out_sr: int = None) -> bytes:
    """轉成 M4A(AAC)，並在編碼的同時降採樣至 out_sr。

    降採樣交給 ffmpeg 一併處理，不需另外引入重採樣套件；
    ffmpeg 的 soxr 重採樣器品質已足夠，且省下一次陣列複製。
    """
    out_sr = out_sr or TARGET_SR

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
        sf.write(t.name, wf, sr, subtype="PCM_16")
        wav_path = t.name

    # 用 with_suffix 換副檔名：字串 replace 會誤傷路徑中其他 ".wav" 片段
    m4a_path = str(Path(wav_path).with_suffix(".m4a"))
    try:
        # capture_output 才拿得到 ffmpeg 的錯誤原因（check=True 只給你一個 exit code）
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", wav_path,
                "-ar", str(out_sr),      # 降採樣（原 32000 → 22050）
                "-ac", "1",
                "-c:a", "aac", "-b:a", AAC_BITRATE,
                m4a_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 轉檔失敗 (exit {result.returncode}): {result.stderr[:300]}")
        with open(m4a_path, "rb") as f:
            return f.read()
    finally:
        for p in (wav_path, m4a_path):
            if os.path.exists(p):
                os.remove(p)


# ───────────────────── FastAPI ─────────────────────

@app.on_event("startup")
async def startup():
    global genai_configured
    key = os.getenv("GEMINI_API_KEY")
    if key:
        genai.configure(api_key=key)
        genai_configured = True
        logger.info("✅ Gemini API 配置成功")
    else:
        logger.warning("⚠️ 未設定 GEMINI_API_KEY，只能用 skip_gemini=true 模式")

    logger.info(f"GPT-SoVITS API: {GSV_API}")
    logger.info(f"參考音: {GSV_REF_AUDIO}")
    logger.info(f"拆句上限: {MAX_SEG_LEN} 字")
    logger.info(f"輸出格式: {DEFAULT_FORMAT}（目標取樣率 {TARGET_SR}Hz, {AAC_BITRATE}）")

    if TAIGI_DICT_ENABLED:
        load_taigi_dict()
        logger.info(f"字典門檻: 覆蓋率 ≥ {TAIGI_DICT_MIN_COVERAGE:.0%} 才免呼叫 Gemini")
    else:
        logger.info("本地字典: 停用（TAIGI_DICT_ENABLED=0）")

    if TAIGI_CACHE_ENABLED:
        load_taigi_cache()
        logger.info(f"轉換快取: 啟用（上限 {TAIGI_CACHE_MAX} 筆，{TAIGI_CACHE_PATH}）")
    else:
        logger.info("轉換快取: 停用（TAIGI_CACHE_ENABLED=0）")

    # 這個路徑是給 GPT-SoVITS 那一端解析的；本服務跑在容器裡時看不到宿主機的檔案，
    # 所以找不到只是提醒，不是錯誤。
    if not Path(GSV_REF_AUDIO).exists():
        logger.warning(
            f"ℹ️ 本機看不到參考音 {GSV_REF_AUDIO}"
            "（若 GPT-SoVITS 在宿主機／別台機器上，這是正常的）"
        )

    if WARMUP_ENABLED:
        asyncio.create_task(_warmup())


async def _warmup():
    """對 GPT-SoVITS 送一次短句，吃掉首次推論的初始化成本。

    以背景工作執行，不阻擋服務啟動 —— 網關的健康檢查不必等預熱完成。
    """
    try:
        t0 = time.perf_counter()
        segs = split_for_tts(WARMUP_TEXT)
        await synthesize_all(segs, 1.0)
        logger.info(f"🔥 預熱完成（{time.perf_counter()-t0:.1f} 秒），首句不再卡頓")
    except Exception as e:
        logger.warning(f"預熱失敗（不影響服務）：{e}")


@app.on_event("shutdown")
async def shutdown():
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()


@app.get("/")
async def root():
    gsv_ok = False
    try:
        r = await get_client().get(f"{GSV_API}/docs", timeout=5)
        gsv_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "status": "running",
        "service": "台語TTS (GPT-SoVITS F1)",
        "ready": gsv_ok and genai_configured,
        "gsv_api": GSV_API,
        "gsv_reachable": gsv_ok,
        "gemini_configured": genai_configured,
        "max_seg_len": MAX_SEG_LEN,
        "warmup": WARMUP_ENABLED,
        "output_format": DEFAULT_FORMAT,
        "output_sample_rate": TARGET_SR,
        "aac_bitrate": AAC_BITRATE,
        "dict": {
            "enabled": TAIGI_DICT_ENABLED,
            "entries": len(_taigi_dict),
            "min_coverage": TAIGI_DICT_MIN_COVERAGE,
            "lenient_coverage": TAIGI_DICT_LENIENT_COVERAGE,
            "hits": _dict_hits,
        },
        "cache": {
            "enabled": TAIGI_CACHE_ENABLED,
            "entries": len(_taigi_cache),
            "hits": _cache_hits,
        },
        "gemini_calls": _gemini_calls,
    }


@app.post("/api/synthesize", response_model=TTSResponse)
async def synthesize(request: TTSRequest):
    try:
        if not request.text.strip():
            raise HTTPException(400, "文字不可為空")

        fmt = request.format.lower()
        if fmt not in ("wav", "m4a"):
            raise HTTPException(400, "format 只支援 wav 或 m4a")

        _t0 = time.perf_counter()

        # 1. 中文 → 台語漢字
        if request.skip_gemini:
            taigi = request.text.strip()
        else:
            if not genai_configured:
                raise HTTPException(503, "Gemini 未配置（或改用 skip_gemini=true）")
            taigi = await chinese_to_taigi(request.text)

        _t_gemini = time.perf_counter()
        logger.info(f"├ Gemini 轉換 {_t_gemini-_t0:.2f}s")

        # 2. 醫療詞替換
        taigi = apply_replacements(taigi)

        # 3. 拆句
        segments = split_for_tts(taigi)
        if not segments:
            raise HTTPException(400, "轉換後為空")

        # 4. 逐段合成 + 串接
        wf, dur, sr = await synthesize_all(segments, request.speed)
        _t_synth = time.perf_counter()
        logger.info(f"├ 合成總計 {_t_synth-_t_gemini:.2f}s（產出 {dur:.1f}s 音訊）")

        # 5. 編碼輸出。m4a 會在編碼時一併降採樣，回報的取樣率要跟著改，
        #    否則前端拿到的 sample_rate 與實際檔案不符。
        if fmt == "m4a":
            audio_bytes = to_m4a_bytes(wf, sr)
            out_sr = TARGET_SR
        else:
            audio_bytes = to_wav_bytes(wf, sr)
            out_sr = sr

        b64 = base64.b64encode(audio_bytes).decode()
        _t_enc = time.perf_counter()
        logger.info(f"├ 編碼 {_t_enc-_t_synth:.2f}s")
        logger.info(
            f"└ 總計 {_t_enc-_t0:.2f}s ｜ {fmt} {len(audio_bytes)//1024}KB "
            f"@ {out_sr}Hz ｜ 音訊 {dur:.1f}s"
        )

        return TTSResponse(
            success=True,
            tailo_romanization=taigi,   # deprecated，相容舊欄位；請改用 taigi_hanji
            taigi_hanji=taigi,
            original_text=request.text,
            segments=segments,
            audio_base64=b64,
            audio_format=fmt,
            audio_duration=dur,
            sample_rate=out_sr,
        )

    except HTTPException:
        raise
    except Exception as e:
        # 內部失敗要回 5xx，不能回 200 + success:false（見審查報告 C18）
        logger.exception("合成失敗")
        return JSONResponse(
            status_code=500,
            content=TTSResponse(
                success=False,
                original_text=request.text,
                error=str(e),
            ).model_dump(),
        )


@app.post("/api/convert")
async def convert_only(request: TTSRequest):
    """只做文字轉換不合成語音。

    同時回報字典覆蓋率與未收錄詞 —— 依 misses 逐步補字典，
    覆蓋率就會提高，Gemini 呼叫也會越來越少。
    """
    dict_out, coverage, misses = dict_convert(request.text)
    taigi = await chinese_to_taigi(request.text)
    replaced = apply_replacements(taigi)
    return {
        "original": request.text,
        "dict_only": dict_out,
        "dict_coverage": round(coverage, 3),
        "dict_misses": misses,
        "used_gemini": coverage < TAIGI_DICT_MIN_COVERAGE,
        "taigi_raw": taigi,
        "taigi_final": replaced,
        "segments": split_for_tts(replaced),
    }


class WarmRequest(BaseModel):
    texts: List[str]


@app.post("/api/cache/warm")
async def warm_cache(request: WarmRequest):
    """預先轉換一批句子。

    問診的固定句（紅旗篩檢、確認語等）可在展示前先跑過一次，
    正式使用時即為快取命中，不必等 Gemini。
    """
    if not genai_configured:
        raise HTTPException(503, "Gemini 未配置")

    hit, new, failed = 0, 0, []
    for t in request.texts:
        key = t.strip()
        if not key:
            continue
        if key in _taigi_cache:
            hit += 1
            continue
        try:
            await chinese_to_taigi(key)
            new += 1
        except Exception as e:
            failed.append({"text": key, "error": str(e)[:120]})

    return {
        "already_cached": hit,
        "newly_cached": new,
        "failed": failed,
        "total_entries": len(_taigi_cache),
    }


@app.delete("/api/cache")
async def clear_cache():
    """清空快取。改了 prompt 之後轉換結果會變，此時需要清掉重建。"""
    global _taigi_cache, _cache_hits, _cache_misses
    n = len(_taigi_cache)
    _taigi_cache = {}
    _cache_hits = _cache_misses = 0
    await asyncio.to_thread(save_taigi_cache)
    return {"cleared": n}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
