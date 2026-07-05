import json
import re
import uuid
from config import Settings
from recommend import recommend
from schedule import SESSIONS_DESC
from models import (
    ChatRequest, TriageResult, TriageCase, HistoryRecord,
    PatientInput, Triage, ConversationState, RecommendRequest,
    Availability, Preferences,
)

def collect_symptoms(chat_request: ChatRequest) -> TriageResult:
    
    message = chat_request.message 
    triage_case = chat_request.triage_case

    if triage_case is None:
        case_id = str(uuid.uuid4())[:8].upper()
        triage_case = TriageCase(case_id=case_id)
        print(f"  建立新病歷：{case_id}")
    else:
        print(f"  沿用病歷：{triage_case.case_id}")

    triage_case.history_records.append(HistoryRecord(role="user", content=message))

    history_str = ""
    for msg in triage_case.history_records:
        role_label = "使用者" if msg.role == "user" else "助理"
        history_str += f"{role_label}：{msg.content}\n"


    current_input = triage_case.patient_input

    prompt = f"""你是台北榮民總醫院的分診助理，正在透過對話收集病患症狀。

目前對話紀錄：
{history_str}

目前已收集到的症狀資料：
{current_input.model_dump_json(indent=2)}

你的任務：
1. 根據對話更新症狀資料
2. 每次都要依「台灣急診五級檢傷分類(TTAS) 民眾衛教版」判斷急迫程度（級數數字越小越嚴重），規則如下：

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
  只要沒有明確命中上面「重」(第一、二級) 或「中」(第三級) 清單裡的項目，一律歸此類。

【TTAS 判級的原則】
1. 嚴格按上方 TTAS 清單逐條比對：只有症狀「明確符合」清單某一項才判該級。
2. red_flags 填入觸發「重」（第一、二級）的症狀描述，沒有就空陣列。

【資料收集原則】
1. 足夠條件：必須要有 symptom + body_part + duration + severity（問病患「輕微／中等／劇烈」）+ onset（問「症狀是突然開始，還是慢慢變嚴重」）+
  accompanying_symptoms。
2. 不夠 → is_complete=false，只問「下一個」最重要的問題。
3. 足夠 → is_complete=true。
4. 問法：每次只問一題、用白話讓長輩聽得懂、已答過的不重複問（病患可能一次答多項）。

【回覆格式規定】
1. TTAS 判斷為「重」  (high)：reply=「您的狀況可能屬於緊急情況，請立即前往急診就醫。（症狀摘要一句）」
  例如：您的狀況可能屬於緊急情況，請立即前往急診就醫。（持續胸痛冒冷汗）
  不論資料是否齊全，立刻設 is_complete=true、warning_required=true，停止追問、不要再問任何問題。
2. 還要繼續問：reply 格式必須是「了解，[下一個問題]」。
  例如：「了解，請問已經持續幾天了？」
3. 資料收集完成且TTAS為「中」(medium)：reply 格式必須是「[症狀摘要，一句話]，建議您盡早就醫」
  例如：「下腹部疼痛一天、中等程度、伴隨發燒，建議您盡早就醫」
4. 資料收集完成且TTAS為「低」(low)：reply 格式必須是「[症狀摘要，一句話]」
  例如：「輕微流鼻水兩天、無發燒」
5. 上述情況都只摘要病患症狀，不要推薦或提到任何科別，格式也嚴格執行上述規定。


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

    reply = "抱歉，我沒聽清楚，請再說一次。"
    try:
        ai_result = json.loads(response)
        if "patient_input" in ai_result:
            new_pi = PatientInput(**ai_result["patient_input"])
            new_pi.age = triage_case.patient_input.age       
            new_pi.gender = triage_case.patient_input.gender
            triage_case.patient_input = new_pi
        if "conversation_state" in ai_result:
            triage_case.conversation_state = ConversationState(**ai_result["conversation_state"])
        if "triage" in ai_result:        
            triage_case.triage = Triage(**ai_result["triage"])
        reply = ai_result.get("reply", "")
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"  AI 回應解析失敗，保留原值：{e}")

    triage_case.history_records.append(HistoryRecord(role="assistant", content=reply))

    is_complete = triage_case.conversation_state.is_complete
    
    triage_result = TriageResult(
        case_id=triage_case.case_id,
        triage_case=triage_case,
        conversation_state=triage_case.conversation_state,
        triage=triage_case.triage,
        department_result=None,             
        next_question=None,
        reply=reply,                        
        needMoreInfo=not is_complete        
    )
    return triage_result


BASIC_INFO_QUESTIONS = """請先提供病患基本資料（可以用一段話回答）：

1. 【年齡】請填數字（例如：45）
2. 【性別】請填 男 / 女"""


def parse_basic_info(chat_request: ChatRequest) -> TriageCase:
    answer = chat_request.message
    triage_case = chat_request.triage_case or TriageCase(case_id=str(uuid.uuid4())[:8].upper())

    m = re.search(r"\d+", answer)                       
    triage_case.patient_input.age = int(m.group()) if m else None
    if "男" in answer:
        triage_case.patient_input.gender = "男"
    elif "女" in answer:
        triage_case.patient_input.gender = "女"

    return triage_case


AVAILABILITY_QUESTIONS = f"""請回答以下三個問題（可以用一段話回答）：

1. 【方便看診時段】您哪幾天的哪個時段方便看診？請把「星期」和「時段」一起回答。
   時段有 {SESSIONS_DESC} 三種。
   （例如：週二早上、週三下午、週四早上和下午）

2. 【看診考量】您希望「掛到最準確的科別（科別優先）」，
   還是「盡快有門診可以看（時間優先）」？
   （請回答：科別 / 時間）

3. 【指定醫師】有沒有特別想看的醫師？
   （有就填醫師名字，沒有請填「不限」）"""


def parse_availability_answer(chat_request: ChatRequest) -> TriageCase:
    user_answer = chat_request.message          
    triage_case = chat_request.triage_case       

    prompt = f"""病患回答了以下就診偏好問題：
「{user_answer}」

問題對應的欄位說明：
- 方便看診時段 → available_slots（「星期+時段」組合的陣列）。
    每一筆是一個 {{"day": "週X", "session": "早上/下午/夜診"}}。
    day 只能是 週一、週二、週三、週四、週五、週六、週日。
    session 只能是 早上、下午、夜診。
    要把「週四早上和下午」這種展開成兩筆：{{"day":"週四","session":"早上"}}、{{"day":"週四","session":"下午"}}。
    病患沒說明確時段就回空陣列 []。
- 看診考量 → specialty_priority（布林，科別優先=true，時間優先=false，預設 true）
- 指定醫師 → doctor_preference（字串，有說名字就填名字，沒有填「不限」）

請解析病患回答並輸出以下 JSON，不要輸出任何其他文字：
{{
  "availability": {{
    "available_slots": [{{"day": "週X", "session": "早上/下午/夜診"}}]
  }},
  "preferences": {{
    "specialty_priority": true 或 false,
    "doctor_preference": "醫師名字或不限",
    "hospital_preference": "台北榮總"
  }}
}}"""

    llm = Settings.llm
    response = str(llm.complete(prompt)).strip().replace("```json", "").replace("```", "").strip()
    print(f"  AI 回應：{response}")

    try:
        ai_result = json.loads(response)
        if "availability" in ai_result:
            triage_case.availability = Availability(**ai_result["availability"])
        if "preferences" in ai_result:
            triage_case.preferences = Preferences(**ai_result["preferences"])
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"  解析失敗，保留預設值：{e}")

    return triage_case



def main():
    print(BASIC_INFO_QUESTIONS)
    basic_answer = input("\n請回答：").strip()
    triage_case = parse_basic_info(ChatRequest(message=basic_answer, triage_case=None))
    print(f"  建立新病歷：{triage_case.case_id}"
          f"（年齡 {triage_case.patient_input.age}、性別 {triage_case.patient_input.gender}）")

    print("\n進入互動模式（輸入 q 結束）\n")

    while True:
        user_input = input("請輸入您的問題：").strip()
        if user_input.lower() == "q":
            break
        if not user_input:
            continue

        chat_request = ChatRequest(message=user_input, triage_case=triage_case)
        current_stage = triage_case.conversation_state.stage if triage_case else "collecting"

        if current_stage == "collecting_availability":
            triage_case = parse_availability_answer(chat_request)
            triage_case.conversation_state.stage = "complete"
            triage_case.conversation_state.is_complete = True

            urgency = triage_case.triage.urgency_level or "low"
            urgency_label = {"high": " 高（請立即急診）", "medium": " 中（盡快就醫）", "low": " 低（一般門診）"}.get(urgency, urgency)

            
            final_result = TriageResult(
                case_id=triage_case.case_id,
                triage_case=triage_case,
                conversation_state=triage_case.conversation_state,
                triage=triage_case.triage,
                department_result=None,
                next_question=None,
                reply="感謝您的回答，資料已收集完成！",
                needMoreInfo=False
            )
            print(final_result.model_dump_json(indent=2))
            print("─" * 50)
            print(f"  急迫程度：{urgency_label}")
            slots = triage_case.availability.available_slots
            slots_str = "、".join(f"{s.day}{s.session}" for s in slots) if slots else "（未指定，不限時段）"
            print(f"  方便時段：{slots_str}")
            print(f"  看診考量：{'科別優先' if triage_case.preferences.specialty_priority else '時間優先'}")
            print(f"  指定醫師：{triage_case.preferences.doctor_preference}")
            print("=" * 50)
            print(" 偏好收集完成")
            print("=" * 50)

            
            preference = "科別優先" if triage_case.preferences.specialty_priority else "時間優先"
            recommend_result = recommend(RecommendRequest(
                triage_case=triage_case,   
                preference=preference
            ))
            print("\n" + "=" * 50)
            print("分診與科別推薦結果（RecommendationResult）")
            print("=" * 50)
            
            if triage_case.triage.urgency_level == "medium":
                print("  緊急程度：中（TTAS 第三級）→ 建議盡快於當日或隔天就診")
            print(recommend_result.model_dump_json(indent=2))
            print("=" * 50)
            print()
            triage_case = None

        else:
            result = collect_symptoms(chat_request)
            triage_case = result.triage_case

            if triage_case.triage.urgency_level == "high":
                print(result.model_dump_json(indent=2))
                triage_case = None
                continue

            if result.needMoreInfo:
                print(result.model_dump_json(indent=2))
                print(f"   AI 問題：{result.reply}")
               

            else:
                
                triage_case.conversation_state.stage = "collecting_availability"
                combined_reply = f"{result.reply}\n\n{AVAILABILITY_QUESTIONS}"
                avail_result = TriageResult(
                    case_id=triage_case.case_id,
                    triage_case=triage_case,
                    conversation_state=triage_case.conversation_state,
                    triage=triage_case.triage,
                    department_result=None,
                    next_question=None,
                    reply=combined_reply,
                    needMoreInfo=True  
                )
                print(avail_result.model_dump_json(indent=2))
                print("─" * 50)
                print(f"AI回覆：{avail_result.reply}")   
                print("─" * 50)
                print(" 症狀收集完成，請再回答就診偏好問題")
                print("─" * 50)


if __name__ == "__main__":
    main()



