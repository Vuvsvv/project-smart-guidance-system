import json
import uuid
from datetime import datetime

from config import Settings          
from database import (
    get_departments_with_category,   
    get_available_schedules,         
)
from dept_keywords import match_candidate_depts 

# ─────────────────────────────────────────
# 分診與科別推薦
#
#   輸入：RecommendRequest（內含資料流1產出的同一份 triage_case）
#   輸出：RecommendationResult（兩欄推薦 + 備選科別）
#
#   point 1~2：接收並解析 RecommendRequest
#   point 3  ：AI 分診（關鍵字前處理 → AI 選科別）
#   point 4  ：把 department_result 寫回 triage_case
#   point 5  ：查 DB 取可掛班表
#   point 6  ：算 score，組 RecommendationItem
#   point 7  ：依權重分成 specialty_first / time_first 兩欄
#   point 8  ：組 RecommendationResult 回傳
# ─────────────────────────────────────────



TODAY = "2026-06-01"

_WEEKDAY_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


# ═══════════════════════════════════════════════════════
# point 3：AI 分診（含關鍵字前處理）
# ═══════════════════════════════════════════════════════
def recommend_department(patient_input: dict) -> dict:
    """
    回傳 DepartmentResult：
      {parentDept, childDept, confidence, reason[]}
    confidence 用混合法：AI 自報 × 關鍵字命中比例修正。
    """

    hits = match_candidate_depts(patient_input)  
    total_hits = sum(hits.values())


    all_depts = get_departments_with_category()
    candidate_lines = "\n".join(
        f"- {d['parentDept']} / {d['childDept']}" for d in all_depts
    )

    prompt = f"""你是台北榮民總醫院的分診助理。以下是病患症狀資料：
{json.dumps(patient_input, ensure_ascii=False, indent=2)}

可選擇的科別清單（必須從中挑一個，parentDept 與 childDept 要完全照抄）：
{candidate_lines}

請判斷最適合的「父科別 + 子科別」，輸出以下 JSON，不要輸出任何其他文字：
{{
  "parentDept": "父科別（完全照抄清單）",
  "childDept": "子科別（完全照抄清單）",
  "confidence": 0.0 到 1.0 的數字,
  "reason": ["推薦理由1", "推薦理由2"]
}}"""

    llm = Settings.llm
    response = str(llm.complete(prompt)).strip().replace("```json", "").replace("```", "").strip()
    print(f"  AI 分診回應：{response}")

    try:
        ai_result = json.loads(response)
    except json.JSONDecodeError:
        print("  分診 JSON 解析失敗，退回第一個科別")
        fallback = all_depts[0]
        ai_result = {
            "parentDept": fallback["parentDept"],
            "childDept": fallback["childDept"],
            "confidence": 0.5,
            "reason": ["AI 回應解析失敗，使用候選清單第一筆"],
        }

    child = ai_result.get("childDept", "")
    confidence_ai = float(ai_result.get("confidence", 0.5))


    if total_hits > 0:
        kw_ratio = hits.get(child, 0) / total_hits
        confidence = round(0.5 * confidence_ai + 0.5 * kw_ratio, 2)
    else:
        confidence = round(confidence_ai, 2)

    return {
        "parentDept": ai_result.get("parentDept", ""),
        "childDept": child,
        "confidence": confidence,
        "reason": ai_result.get("reason", []),
    }

def _date_factor(date_str: str) -> float:
    """日期越接近 TODAY 越高：1/(1+天數差)，正規化 0~1。"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        base = datetime.strptime(TODAY, "%Y-%m-%d").date()
        days = max((d - base).days, 0)
        return 1.0 / (1.0 + days)
    except ValueError:
        return 0.0


TAG_NEUTRAL = 0.5   


def _is_informative_tag(detail_tag: str, child_dept: str) -> bool:
    """
    detail_tag 是「醫院貼在該門診上的標籤」。只有當它是『具體次專長』時才值得 AI 評分：
      - 空白（醫院沒填）           → 不評（無資訊）
      - 等於科別名（只是重複科別） → 不評（無額外資訊）
      - 其餘                       → 具體次專長，值得評分
    實測全院僅約 1.6% 的門診屬於此類。
    """
    if not detail_tag:
        return False
    return detail_tag.strip() != (child_dept or "").strip()


def score_tags_with_ai(distinct_tags: list[str], patient_input: dict) -> dict:
    """
    一次 AI 呼叫，替一組『具體次專長』標籤各打 0~1 的症狀相符分。
    讓 AI 跨越「病患白話症狀 ↔ 專業次專長詞」的語意落差。
    回傳 {tag: score}；distinct_tags 為空則不呼叫 AI、回空 dict。
    """
    if not distinct_tags:
        return {}

    tag_lines = "\n".join(f"- {t}" for t in distinct_tags)
    prompt = f"""你是醫療分診助理。以下是某科別門診的「醫師次專長標籤」清單：
{tag_lines}

病患的症狀資料（已由分診對話整理）：
{json.dumps(patient_input, ensure_ascii=False, indent=2)}

請判斷每個次專長標籤與這位病患症狀的相符程度，給 0.0~1.0 的分數：
- 病患症狀「明確指向」該次專長 → 高分（0.7~1.0）
- 沒有特別指向、不確定 → 中性（約 0.5）
- 明顯不相關 → 低分（0.0~0.3）
注意：病患症狀是白話（如「胸悶、心悸」），標籤是專業詞（如「心房顫動電燒」），
請用你的醫學知識判斷語意相關性，不要只看字面。

只輸出 JSON，不要其他文字，格式為 {{"標籤": 分數, ...}}，標籤需與清單完全一致。"""

    llm = Settings.llm
    response = str(llm.complete(prompt)).strip().replace("```json", "").replace("```", "").strip()
    print(f"  AI 專長評分：{response}")
    try:
        result = json.loads(response)
        # 僅保留清單內的標籤、且分數可轉 float
        return {t: float(result[t]) for t in distinct_tags if t in result}
    except (json.JSONDecodeError, TypeError, ValueError):
        print("  專長評分解析失敗，全部視為中性")
        return {}


def _weekday_zh(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return _WEEKDAY_ZH[d.weekday()]
    except ValueError:
        return ""


def _slot_match(row: dict, slots: list) -> bool:
    """
    row 的（星期,時段）是否落在病患 available_slots 任一組合內。
    slots 為空 → 視為無時段限制，一律通過。
    """
    if not slots:
        return True
    day = _weekday_zh(row["date"])
    return any(s.get("day") == day and s.get("session") == row["session"] for s in slots)


def _row_tag(row: dict, tag_scores: dict, child_dept: str) -> float:
    """這筆門診的專長相符度（0~1）。非具體次專長（空白/科別名）一律中性 0.5。"""
    if _is_informative_tag(row["detail_tag"], child_dept):
        return tag_scores.get(row["detail_tag"], TAG_NEUTRAL)
    return TAG_NEUTRAL


def _build_items(rows, department_result, tag_scores, slots,
                 specialty_priority=True, sort_by_date=False):
    """
    把班表組成 RecommendationItem 清單並排序（最多前 5 筆）。
    排序（最後一步，無加權，兩層排序）：
      sort_by_date=True       → 純依日期最近（放寬 fallback 用「最接近」）
      specialty_priority=True → 科別優先：專長(高→低) → 日期(近→遠)
      specialty_priority=False→ 時間優先：日期(近→遠) → 專長(高→低)
    """
    child_dept = department_result["childDept"]
    items = []
    for row in rows:
        f_tag = _row_tag(row, tag_scores, child_dept)
        reasons = []
        if f_tag >= 0.7:
            reasons.append("醫師次專長相符")
        if _date_factor(row["date"]) >= 0.5:
            reasons.append("近期可掛")
        if _slot_match(row, slots):
            reasons.append("符合您方便時段")
        if not reasons:
            reasons.append("可掛號")
        items.append({
            "recommendation_id": "rec_" + uuid.uuid4().hex[:6],
            "parentDept": department_result["parentDept"],
            "childDept": row["childDept"],
            "doctor": row["doctor"],
            "date": row["date"],
            "session": row["session"],
            "room": row["room"],
            "specialty_match": round(f_tag, 2),  
            "reasons": reasons,
        })

    if sort_by_date:
        items.sort(key=lambda x: x["date"])
    elif specialty_priority:
        items.sort(key=lambda x: (-x["specialty_match"], x["date"]))   # 專長 → 日期
    else:
        items.sort(key=lambda x: (x["date"], -x["specialty_match"]))   # 日期 → 專長
    return items[:5]



def _fallback_departments(department_result: dict) -> list[dict]:
    all_depts = get_departments_with_category()
    parent = department_result["parentDept"]
    child = department_result["childDept"]
    siblings = [d for d in all_depts
                if d["parentDept"] == parent and d["childDept"] != child]
    return [{
        "parentDept": d["parentDept"],
        "childDept": d["childDept"],
        "reason": f"{child}近期無號時，可改掛同屬「{parent}」的{d['childDept']}",
    } for d in siblings]



# point 1~2 + 串接 3~8
def recommend(request: dict) -> dict:
    """
    request（RecommendRequest）：
      {
        "triage_case": {...資料流1產出的同一份病歷...},
        "userQuery": "幫我找明天下午的號",
        "preference": "科別優先" 或 "時間優先"
      }
    """
    # ── point 1~2：解析 RecommendRequest ──
    triage_case = request["triage_case"]
    patient_input = triage_case["patient_input"]
    availability = triage_case.get("availability", {})
    preferences = triage_case.get("preferences", {})
    case_id = triage_case.get("case_id")

    # ── point 3：AI 分診 ──
    department_result = recommend_department(patient_input)

    # ── point 4：寫回 triage_case ──
    triage_case["department_result"] = department_result

    # ── point 5：查 DB 取該科全部可掛班表（全時段） ──
    child = department_result["childDept"]
    all_rows = get_available_schedules(child, TODAY)
    slots = availability.get("available_slots") or []   # [{"day","session"}]，空=無限制

    # ── point 5b：指定醫師（先篩出該醫師的號） ──
    doctor_pref = (preferences.get("doctor_preference") or "不限").strip()
    has_doctor = bool(doctor_pref and doctor_pref != "不限")
    doc_rows = [r for r in all_rows if doctor_pref in r["doctor"]] if has_doctor else all_rows

    # ── point 5c：用病患可來時段（星期+時段）硬篩，並處理無交集的放寬 ──
    feasible = [r for r in doc_rows if _slot_match(r, slots)]
    relaxed_by_date = False

    if feasible and has_doctor:
        print(f"  指定醫師「{doctor_pref}」：推薦其門診（{len(feasible)} 筆）")

    if not feasible and has_doctor:
        # 指定醫師×時段無交集 → 丟掉醫師、保留時段，改推同科其他醫師
        feasible = [r for r in all_rows if _slot_match(r, slots)]
        if feasible:
            print(f"  指定醫師「{doctor_pref}」在您方便的時段近期無門診，改推同科其他醫師")

    if not feasible:
        # 時段整個沒號 → 丟掉時段限制，推該科最近可掛的號當參考
        if slots:
            print("  您方便的時段近期無可掛號，以下為最接近的參考")
        feasible = doc_rows if (has_doctor and doc_rows) else all_rows
        relaxed_by_date = True

    # ── point 6 前置：專長分由 AI 判斷（只評「具體次專長」標籤，多數門診不觸發） ──
    distinct_tags = sorted({
        r["detail_tag"] for r in feasible
        if _is_informative_tag(r["detail_tag"], child)
    })
    tag_scores = score_tags_with_ai(distinct_tags, patient_input)

    # ── point 6~7：最後一步排序——科別優先(專長→日期) / 時間優先(日期→專長) ──
    specialty_priority = preferences.get("specialty_priority", True)
    recommendations = _build_items(feasible, department_result, tag_scores, slots,
                                   specialty_priority=specialty_priority,
                                   sort_by_date=relaxed_by_date)

    # ── point 8：該科完全沒有可掛號 → 補同父科別 fallback ──
    fallback = [] if all_rows else _fallback_departments(department_result)

    # 嚴格回傳 RecommendationResult（扁平單一清單）。
    # 只回使用者選的那一種排序的前 5 筆；department_result 已 in-place 寫回 triage_case。
    return {
        "case_id": case_id,
        "recommendations": recommendations,
        "fallback_departments": fallback,
    }



def main():
    print("=" * 50)
    print("資料流2：分診與科別推薦（驗證模式）")
    print("=" * 50)

 
    demo_request = {
        "triage_case": {
            "case_id": "A1B2C3D4",
            "patient_input": {
                "symptom": "頭痛",
                "body_part": "頭部",
                "duration": "3天",
                "severity": "劇烈",
                "onset": "突然",
                "accompanying_symptoms": ["發燒", "頸部僵硬"],
                "red_flags": [],
            },
            "availability": {
                "available_slots": [
                    {"day": "週一", "session": "早上"},
                    {"day": "週三", "session": "早上"},
                ],
                "can_take_leave": False,
            },
            "preferences": {
                "specialty_priority": True,
                "doctor_preference": "不限",
                "hospital_preference": "台北榮總",
            },
            "triage": {
                "urgency_level": "medium",
                "urgency_score": 50,
            },
            "department_result": None,
        },
        "userQuery": "幫我找最近可以看的號",
        "preference": "科別優先",
    }

    result = recommend(demo_request)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
