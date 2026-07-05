import json
from config import Settings
from models import PatientInput

TAG_NEUTRAL = 0.5


def _has_specialty(specialty: str) -> bool:
    return bool((specialty or "").strip())


def score_specialties_with_ai(distinct_specialties: list[str], patient_input: PatientInput):
    if not distinct_specialties:
        return {}, {}

    tag_lines = "\n".join(f"- {t}" for t in distinct_specialties)
    prompt = f"""你是醫療分診助理。以下是某科別候選醫師的「專長描述」清單：
{tag_lines}

病患的症狀資料：
{patient_input.model_dump_json(indent=2)}

請判斷每位醫師的專長描述與這位病患症狀的相符程度，並做兩件事：
1. 給 0.0~1.0 的相符分數（score）：
   - 病患症狀「明確指向」該專長 → 高分（0.7~1.0）
   - 沒有特別指向、不確定 → 中性（0.5）
   - 明顯不相關 → 低分（0.0~0.3）
2. 從該專長描述中「只挑出跟病患症狀相符的專長項目」（matched），用頓號分隔；
   若整串都不相符則給空字串。
注意：病患症狀是白話（如「胸悶、心悸」），專長描述是專業詞（如「心律不整、心臟電生理」），
請用你的醫學知識判斷語意相關性，不要只看字面。

只輸出 JSON，不要其他文字，格式為：
{{"專長描述": {{"score": 分數, "matched": "相符的專長項目"}}, ...}}
「專長描述」的 key 需與清單完全一致。"""

    llm = Settings.llm
    response = str(llm.complete(prompt)).strip().replace("```json", "").replace("```", "").strip()
    print(f"  AI 專長評分：{response}")
    scores, matched = {}, {}
    try:
        result = json.loads(response)
        for t in distinct_specialties:
            if t in result and isinstance(result[t], dict):
                scores[t] = float(result[t].get("score", TAG_NEUTRAL))
                matched[t] = str(result[t].get("matched", "") or "")
        return scores, matched
    except (json.JSONDecodeError, TypeError, ValueError):
        print("  專長評分解析失敗，全部視為中性")
        return {}, {}


def _row_tag(row: dict, tag_scores: dict) -> float:
    if _has_specialty(row["specialty_tags"]):
        return tag_scores.get(row["specialty_tags"], TAG_NEUTRAL)
    return TAG_NEUTRAL
