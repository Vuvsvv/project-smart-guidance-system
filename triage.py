import json
import uuid
from config import Settings         
from database import get_db_connection, get_active_dept_names  
from recommend import recommend      

# ─────────────────────────────────────────
#  第一段：收集症狀（AI 追問）
#
#    輸入：ChatRequest
#      - message：使用者這次說的話
#      - triage_case：之前的病歷（第一次傳入時為 None）
#
#    輸出：TriageResult
#      - needMoreInfo: true  → AI 還要繼續問
#      - needMoreInfo: false → 資料夠了，可以讓使用者確認
# ─────────────────────────────────────────
def collect_symptoms(chat_request: dict) -> dict:
    """
    第一段：收集症狀
    每次使用者說話，AI 更新 patient_input 並決定要不要繼續追問
    """
    message = chat_request.get("message", "")    # ← 終端機輸入模擬前端傳來的 JSON
    triage_case = chat_request.get("triage_case")

    # ── 建立或沿用病歷 ──
    if triage_case is None:
        # 初診：建立全新病歷
        case_id = str(uuid.uuid4())[:8].upper()
        triage_case = {
            "case_id": case_id,
            "history_records": [],
            "patient_input": {
                "symptom": "",
                "body_part": None,
                "duration": None,
                "severity": None,
                "onset": None,
                "accompanying_symptoms": [],
                "red_flags": []
            },
            "availability": {
                "available_slots": [],   # list[{"day","session"}]，空=無時段限制
                "can_take_leave": False
            },
            "preferences": {
                "specialty_priority": True,
                "doctor_preference": "不限",
                "hospital_preference": "台北榮總"
            },
            "triage": {
                "urgency_score": None,
                "urgency_level": None,
                "warning_required": False,
                "warning_message": None,
                "need_more_info": True,
                "next_question": None
            },
            "conversation_state": {
                "stage": "collecting",
                "is_complete": False
            },
            "department_result": None
        }
        print(f"  建立新病歷：{case_id}")
    else:
        print(f"  沿用病歷：{triage_case.get('case_id')}")

    # ── 把使用者說的話加進對話紀錄 ──
    triage_case["history_records"].append({
        "role": "user",
        "content": message
    })

    # ── 組對話歷史給 AI 看 ──
    history_str = ""
    for msg in triage_case["history_records"]:
        role_label = "使用者" if msg["role"] == "user" else "助理"
        history_str += f"{role_label}：{msg['content']}\n"

    # ── 現有的 patient_input ──
    current_input = triage_case["patient_input"]

    # ── 呼叫 AI 更新 patient_input、判斷急迫性、決定要不要繼續問 ──
    prompt = f"""你是台北榮民總醫院的分診助理，正在透過對話收集病患症狀。

目前對話紀錄：
{history_str}

目前已收集到的症狀資料：
{json.dumps(current_input, ensure_ascii=False, indent=2)}

你的任務：
1. 根據對話更新症狀資料
2. 每次都要依「台灣急診五級檢傷分類(TTAS) 民眾衛教版」判斷急迫程度（級數數字越小越嚴重）：

【重 → 立即急診】(urgency_level=high, urgency_score=90)　＝ TTAS 第一、二級
  第一級 復甦急救（立即處理）：
    - 心跳、呼吸停止，肢體及嘴唇發青、發紫
    - 體溫 >41°C 或 <32°C
    - 無意識、意識混亂（對疼痛刺激無反應、只能呻吟或說單一字句、只有疼痛刺激才會睜眼）
    - 持續抽搐且無意識
  第二級 危急（10分鐘內）：
    - 急性意識狀態改變（語言與動作遲滯，但尚可溝通）
    - 持續胸悶、胸痛且冒冷汗
    - 低血糖（<40mg/dl）
    - 大量血便、黑便、嘔血
    - 外傷造成之大量出血，頭頸軀幹骨盆部位血流不止
    - 槍傷，頭、頸、軀幹鈍傷、穿刺傷，開放性傷口疑似骨折
    - 高處墜落、車禍（乘客被拋出車外）、頭部撞擊後曾失去意識
    - 突發性視覺改變
    - 免疫功能不全且發燒
    - 會陰部穿刺傷與大量出血，生殖器腫脹變形
    - 外傷或接觸化學物質後出現的神經功能異常（動作與感覺改變）
    - 化學物質濺入眼睛
    - 疑似藥物過敏導致呼吸困難
    - 螫傷、咬傷導致呼吸困難或意識改變

【中 → 當日或隔天門診】(urgency_level=medium, urgency_score=50)　＝ TTAS 第三級
  第三級 緊急（30分鐘內）：
    - 走動時明顯有呼吸急促
    - 經期逾期且腹痛
    - 無法控制的腹瀉或嘔吐
    - 外傷後肢體腫脹變形疑似骨折／脫臼
    - 咖啡色嘔吐物或黑便
    - 高血壓（收縮壓>200mmHg 或 舒張壓>110mmHg）且沒有任何症狀
    - 抽搐後意識已恢復
    - 廣泛性紅疹／水泡
    - 毒氣或其他氣體吸入，無呼吸窘迫徵象
    - 急產（宮縮>2分鐘）
    

【輕 → 一般門診】(urgency_level=low, urgency_score=20)　＝ TTAS 第四、五級
  其餘所有狀況一律歸此類（一般症狀、輕微不適、慢性回診、拿藥），不需特別列舉
3. 判斷資料是否足夠（至少要有 symptom + body_part + duration + serverity(詢問，要求使用者回答症狀輕微、中等、還是劇烈？) + onset + accompanying_symptoms）
4. 如果不夠，提出下一個最重要的問題
5. 如果已經足夠，把 is_complete 設為 true

注意：
- red_flags 填入觸發「重」（第一、二級）的症狀描述（沒有就空陣列）
- 問題要用白話，讓長輩聽得懂
- 每次只問一個問題，回答過的問題就不用重複問
- 使用者有時會回答兩個以上可以做為判斷資料的回答
- 如果是「重」(high)，不論資料是否齊全，立刻設 is_complete 為 true、warning_required 為 true，
  reply 直接告知請立即前往急診，不要再追問任何問題

回覆格式規定：
- 還要繼續問：reply 格式必須是「了解，[下一個問題]」，不要多餘廢話
  例如：「了解，請問已經持續幾天了？」
- 資料收集完成：reply 格式必須是「[症狀摘要，一句話]，建議掛[科別]」
  例如：「發燒三天、喉嚨痛，建議掛一般內科」
- 絕對不要說「感謝您的資訊」「祝您早日康復」「我明白了」這類客套話

請輸出以下 JSON，不要輸出任何其他文字：
{{
  "patient_input": {{
    "symptom": "主要症狀描述",
    "body_part": "哪個部位或 null",
    "duration": "持續多久或 null",
    "severity": "嚴重程度或 null",
    "onset": "怎麼開始的或 null",
    "accompanying_symptoms": ["伴隨症狀列表"],
    "red_flags": ["危險警訊列表"]
  }},
  "triage": {{
    "urgency_score": 數字（low=20, medium=50, high=90）,
    "urgency_level": "low 或 medium 或 high",
    "warning_required": true 或 false,
    "warning_message": "警告訊息或 null",
    "need_more_info": true 或 false,
    "next_question": "下一個要問的問題（need_more_info=true 時必填，false 時填 null）"
  }},
  "conversation_state": {{
    "stage": "collecting",
    "is_complete": true 或 false
  }},
  "reply": "對使用者說的話（格式見上方規定）"
}}"""

    llm = Settings.llm
    response = str(llm.complete(prompt)).strip().replace("```json", "").replace("```", "").strip()
    print(f"  AI 回應：{response}")

    try:
        ai_result = json.loads(response)
    except json.JSONDecodeError:
        print("  JSON 解析失敗，使用預設值")
        ai_result = {
            "patient_input": current_input,
            "conversation_state": {"stage": "collecting", "is_complete": False},
            "reply": "抱歉，我沒聽清楚，可以再說一次嗎？"
        }

    # ── 更新 triage_case ──
    triage_case["patient_input"] = ai_result.get("patient_input", current_input)
    triage_case["conversation_state"] = ai_result.get("conversation_state", {
        "stage": "collecting", "is_complete": False
    })
    # 每次都更新急迫性判斷
    if "triage" in ai_result:
        triage_case["triage"] = ai_result["triage"]

    # ── 把 AI 的回應加進對話紀錄 ──
    reply = ai_result.get("reply", "")
    triage_case["history_records"].append({
        "role": "assistant",
        "content": reply
    })

    is_complete = triage_case["conversation_state"].get("is_complete", False)
    # ── 組成 TriageResult 回傳 ──
    triage_result = {
        "case_id": triage_case["case_id"],
        "triage_case": triage_case,           
        "conversation_state": triage_case["conversation_state"],
        "triage": triage_case["triage"],      
        "department_result": None,             # 第一段不判斷科別，第二段才填
        "next_question": None,
        "reply": reply,                        # AI 這次說的話，前端顯示用
        "needMoreInfo": not is_complete        # 給前端
    }
    return triage_result


# 收集就診偏好（availability + preferences）

AVAILABILITY_QUESTIONS = """請回答以下四個問題（可以用數字列點或一段話回答）：

1. 【方便看診時段】您哪幾天的哪個時段方便看診？請把「星期」和「時段」一起說。
   時段只有早上 / 下午 / 夜診三種。
   （例如：週二早上、週三下午、週四早上和下午）

2. 【能否請假】如果看診時間在平常日，您方便請假嗎？
   （請回答：可以 / 不可以）

3. 【看診考量】您希望「掛到最準確的科別（科別優先）」，
   還是「盡快有門診可以看（時間優先）」？
   （請回答：科別 / 時間）

4. 【指定醫師】有沒有特別想看的醫師？
   （有就填醫師名字，沒有請填「不限」）"""


def parse_availability_answer(user_answer: str, triage_case: dict) -> dict:
    """
    使用者一次回答四個問題後，AI 解析並填入對應欄位：
    available_slots → list[{"day","session"}]（可看診的「星期+時段」組合）
    can_take_leave  → bool（能否請假）
    specialty_priority → bool（True=科別優先, False=時間優先）
    doctor_preference → str（指定醫師或不限）
    """
    prompt = f"""病患回答了以下就診偏好問題：
「{user_answer}」

問題對應的欄位說明：
- 方便看診時段 → available_slots（「星期+時段」組合的陣列）。
    每一筆是一個 {{"day": "週X", "session": "早上/下午/夜診"}}。
    day 只能是 週一、週二、週三、週四、週五、週六、週日。
    session 只能是 早上、下午、夜診（沒有「中午」，中午請歸到下午）。
    要把「週四早上和下午」這種展開成兩筆：{{"day":"週四","session":"早上"}}、{{"day":"週四","session":"下午"}}。
    病患沒說明確時段就回空陣列 []。
- 能否請假 → can_take_leave（布林，可以=true，不可以=false）
- 看診考量 → specialty_priority（布林，科別優先=true，時間優先=false，預設 true）
- 指定醫師 → doctor_preference（字串，有說名字就填名字，沒有填「不限」）

請解析病患回答並輸出以下 JSON，不要輸出任何其他文字：
{{
  "availability": {{
    "available_slots": [{{"day": "週X", "session": "早上/下午/夜診"}}],
    "can_take_leave": true 或 false
  }},
  "preferences": {{
    "specialty_priority": true 或 false,
    "doctor_preference": "醫師名字或不限",
    "hospital_preference": "台北榮總"
  }}
}}"""

    llm = Settings.llm
    response = str(llm.complete(prompt)).strip().replace("```json", "").replace("```", "").strip()
    print(f"  AI 解析回答：{response}")

    try:
        ai_result = json.loads(response)
        triage_case["availability"] = ai_result.get("availability", triage_case["availability"])
        triage_case["preferences"] = ai_result.get("preferences", triage_case["preferences"])
    except json.JSONDecodeError:
        print("  解析失敗，保留預設值")

    return triage_case



# 主程式（模擬終端機對話）
def main():
    print("=" * 50)
    print("台北榮民總醫院導引系統 ")
    print("=" * 50)

    get_active_dept_names()

    print("\n進入互動模式（輸入 q 結束）\n")

    triage_case = None  # 第一次為 None，之後沿用

    while True:
        user_input = input("請輸入您的問題：").strip()
        if user_input.lower() == "q":
            break
        if not user_input:
            continue

        # 組 ChatRequest（模擬前端傳來的 JSON）
        # 真實情況：前端傳 {"message": "...", "triage_case": {...}}
        chat_request = {
            "message": user_input,
            "triage_case": triage_case
        }

        # 根據 stage 決定呼叫哪個函式
        # 這個判斷在真正串 API 後由後端做，你的函式只要根據 triage_case 裡的 stage 決定
        current_stage = triage_case["conversation_state"]["stage"] if triage_case else "collecting"

        if current_stage == "collecting_availability":
            # ── 使用者回答了就診偏好 ──
            # 呼叫 parse_availability_answer 解析並存回 triage_case
            triage_case = parse_availability_answer(user_input, triage_case)
            triage_case["conversation_state"]["stage"] = "complete"
            triage_case["conversation_state"]["is_complete"] = True

            urgency = triage_case["triage"].get("urgency_level", "low")
            urgency_label = {"high": " 高（請立即急診）", "medium": " 中（盡快就醫）", "low": " 低（一般門診）"}.get(urgency, urgency)

            # 最終 TriageResult 回傳後端
            final_result = {
                "case_id": triage_case["case_id"],
                "triage_case": triage_case,
                "conversation_state": triage_case["conversation_state"],
                "triage": triage_case["triage"],
                "department_result": None,
                "next_question": None,
                "reply": "感謝您的回答，資料已收集完成！",
                "needMoreInfo": False
            }
            print(json.dumps(final_result, ensure_ascii=False, indent=2))
            print("─" * 50)
            print(f"  急迫程度：{urgency_label}")
            slots = triage_case['availability']['available_slots']
            slots_str = "、".join(f"{s['day']}{s['session']}" for s in slots) if slots else "（未指定，不限時段）"
            print(f"  方便時段：{slots_str}")
            print(f"  能否請假：{triage_case['availability']['can_take_leave']}")
            print(f"  看診考量：{'科別優先' if triage_case['preferences']['specialty_priority'] else '時間優先'}")
            print(f"  指定醫師：{triage_case['preferences']['doctor_preference']}")
            print("=" * 50)
            print(" 全部收集完成！triage_case 已回傳後端")
            print("=" * 50)

            # ── 資料流2：自動接續分診與科別推薦 ──
            preference = "科別優先" if triage_case["preferences"]["specialty_priority"] else "時間優先"
            recommend_result = recommend({
                "triage_case": triage_case,   # 同一份病歷直接傳入
                "preference": preference
            })
            print("\n" + "=" * 50)
            print(" 資料流2：分診與科別推薦結果（RecommendationResult）")
            print("=" * 50)
            # ── 中（TTAS 第三級）：照常推薦，僅加一句提醒 ──
            if triage_case["triage"].get("urgency_level") == "medium":
                print("  緊急程度：中（TTAS 第三級）→ 建議盡快於當日或隔天就診")
            print(json.dumps(recommend_result, ensure_ascii=False, indent=2))
            print("=" * 50)
            print()
            triage_case = None

        else:
            # ── 症狀收集階段（stage = "collecting"）──
            result = collect_symptoms(chat_request)
            triage_case = result["triage_case"]

            # ── 重（TTAS 一、二級）：直接請去急診，停止追問與後續流程 ──
            if triage_case["triage"].get("urgency_level") == "high":
                print(json.dumps(result, ensure_ascii=False, indent=2))
                print("=" * 50)
                print("   緊急程度：重（疑似 TTAS 第一、二級）")
                print(f"  {result['reply']}")
                print("  → 請立即前往急診，本系統不再進行門診推薦")
                print("=" * 50)
                print()
                triage_case = None
                continue

            if result["needMoreInfo"]:
                # 還在收集症狀，reply 裡有下一個問題，回傳給前端顯示
                print(json.dumps(result, ensure_ascii=False, indent=2))
                print("─" * 50)
                print(" 已回傳後端 → 前端顯示 AI 問題")
                print(f"   AI 問題：{result['reply']}")
                print("─" * 50)

            else:
                # 症狀收集完成，改 stage 為 collecting_availability
                # 把就診偏好問題放進 reply 回傳給前端顯示
                triage_case["conversation_state"]["stage"] = "collecting_availability"
                combined_reply = f"{result['reply']}\n\n{AVAILABILITY_QUESTIONS}"
                avail_result = {
                    "case_id": triage_case["case_id"],
                    "triage_case": triage_case,
                    "conversation_state": triage_case["conversation_state"],
                    "triage": triage_case["triage"],
                    "department_result": None,
                    "next_question": None,
                    # ← 重點：就診偏好問題放在 reply，前端直接顯示這段文字
                    "reply": combined_reply,
                    "needMoreInfo": True  # 還需要使用者繼續回答
                }
                print(json.dumps(avail_result, ensure_ascii=False, indent=2))# 把 Python 的字典，打包成標準的 JSON 字串。
                print("─" * 50)
                print(" 症狀收集完成，請再回答reply就診偏好問題")
                print("─" * 50)


if __name__ == "__main__":
    main()



