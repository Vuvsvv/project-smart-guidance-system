import json
import os
import uuid
import pyodbc
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.google_genai import GoogleGenAI

# ─────────────────────────────────────────
# 0. 載入環境變數
# ─────────────────────────────────────────
load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

# ─────────────────────────────────────────
# 1. 設定 LLM 模型
# ─────────────────────────────────────────
Settings.llm = GoogleGenAI(
    model="gemini-3-flash-preview",
    api_key=GEMINI_API_KEY,
)
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-m3"
)

# ─────────────────────────────────────────
# 2. 資料庫連線
# ─────────────────────────────────────────
def get_db_connection():
    db_password = os.getenv("DB_PASSWORD")
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=medichain-server.database.windows.net;"
        "DATABASE=MediChainDB;"
        "UID=medichain_admin;"
        f"PWD={db_password};"
        "Encrypt=yes;"
        "Connection Timeout=30;"
    )

# ─────────────────────────────────────────
# 3. 載入科別清單（快取）
# ─────────────────────────────────────────
_dept_list_cache = None

def get_active_dept_names() -> list[str]:
    global _dept_list_cache
    if _dept_list_cache is not None:
        return _dept_list_cache
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT dept_name
            FROM Department
            ORDER BY dept_name
        """)
        rows = cursor.fetchall()
        conn.close()
        _dept_list_cache = [row[0] for row in rows]
        print(f"科別清單載入完成（共 {len(_dept_list_cache)} 個科別）")
        return _dept_list_cache
    except Exception as e:
        print(f"載入科別失敗：{e}")
        return []

# ─────────────────────────────────────────
# 4. 第一段：收集症狀（AI 追問）
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
    message = chat_request.get("message", "")
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
                "preferred_days": [],
                "preferred_sessions": [],
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
2. 每次都要判斷急迫程度（紅旗制度）：
   - high（立即急診）：心臟劇烈疼痛、呼吸困難、昏迷、大量出血、中風症狀（臉歪手麻說話不清）、嚴重過敏
   - medium（盡快就醫）：持續高燒、持續嘔吐、劇烈頭痛、視力突然喪失、骨折疑似
   - low（一般門診）：其他慢性或輕微症狀
3. 判斷資料是否足夠（至少要有 symptom + body_part + duration + serverity(詢問，讓使用者回答症狀輕微、中等、還是劇烈？) + onset + accompanying_symptoms）
4. 如果不夠，提出下一個最重要的問題
5. 如果已經足夠，把 is_complete 設為 true

注意：
- red_flags 填入觸發高急迫的症狀描述（沒有就空陣列）
- 問題要用白話，讓長輩聽得懂
- 每次只問一個問題，回答過的問題就不用重複問
- 如果是 high 急迫，立刻設 is_complete 為 true 並告知請去急診

請輸出以下 JSON，不要輸出任何其他文字：
{{
  "patient_input": {{
    "symptom": "主要症狀描述",
    "body_part": "哪個部位或 null",
    "duration": "持續多久或 null",
    "severity": "嚴重程度或 null",
    "onset": "怎麼開始的或 null",
    "accompanying_symptoms": ["伴隨症狀列表"],
    "red_flags": ["危險警訊列表，例如：胸口劇痛"]
  }},
  "triage": {{
    "urgency_score": 數字（low=20, medium=50, high=90）,
    "urgency_level": "low 或 medium 或 high",
    "warning_required": true 或 false,
    "warning_message": "警告訊息或 null",
    "need_more_info": true 或 false,
    "next_question": null
  }},
  "conversation_state": {{
    "stage": "collecting",
    "is_complete": true 或 false
  }},
  "reply": "對使用者說的話（如果還要繼續問就是下一個問題，如果完成就是確認訊息）"
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

    # # ── 組成 TriageResult 回傳 ──
    # return {
    #     "case_id": triage_case["case_id"],
    #     "triage_case": triage_case,
    #     "conversation_state": triage_case["conversation_state"],
    #     "triage": triage_case["triage"],
    #     "department_result": None,   # 第一段不判斷科別，等第二段
    #     "reply": reply,
    #     "needMoreInfo": not is_complete
    # }


# ─────────────────────────────────────────
# 5. 主程式（模擬終端機對話）
# ─────────────────────────────────────────
def main():
    print("=" * 50)
    print("  台北榮民醫院導引系統 ")
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

        # 組 ChatRequest
        chat_request = {
            "message": user_input,
            "triage_case": triage_case
        }

        # 呼叫第一段
        result = collect_symptoms(chat_request)

        # 保存 triage_case 供下次使用
        triage_case = result["triage_case"]

        # 顯示結果
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()

        # 模擬回傳後端再傳回前端的過程
        if result["needMoreInfo"]:
            print("─" * 50)
            print(" 已回傳後端 → 後端轉傳給前端 → 前端顯示 AI 問題")
            print(f"   AI 問題：{result['reply']}")
            print("─" * 50)
        
        # 如果資料收集完成，提示可以進入第二段
        if not result["needMoreInfo"]:
            urgency = result["triage"].get("urgency_level", "low")
            urgency_label = {"high": " 高（請立即急診）", "medium": " 中（盡快就醫）", "low": " 低（一般門診）"}.get(urgency, urgency)
            print("─" * 50)
            print(" 以下是包裝成 TriageResult 格式回傳後端的 JSON：")
            print("─" * 50)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("─" * 50)
            print(f"  急迫程度：{urgency_label}")
            print(f"  red_flags：{result['triage_case']['patient_input']['red_flags']}")
            print("=" * 50)
            print("  症狀收集完成！")
            print("  使用者按確認 → triage_case 傳給後端 → 進行第二段")
            print("=" * 50)
            print()
            # 重置，等待下一位病患
            triage_case = None


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════
# 待補功能（資料庫醫師資料完成後取消註解接上）
# ═══════════════════════════════════════════════════════

# def get_doctors_by_dept(dept_name):
#     """段二：根據科別查詢所有醫師（含 specialty_tags）"""
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("""
#         SELECT d.doctor_id, d.name, d.title, d.specialty_tags, dept.dept_name
#         FROM Doctor d
#         JOIN Department dept ON d.dept_id = dept.dept_id
#         WHERE dept.dept_name = ?
#           AND d.is_active = 1
#     """, dept_name)
#     rows = cursor.fetchall()
#     conn.close()
#     return [{
#         "doctor_id": row[0],
#         "name": row[1],
#         "title": row[2] or "",
#         "specialty_tags": row[3] or "",
#         "dept_name": row[4]
#     } for row in rows]


# def pick_best_doctor(symptom, doctors):
#     """段三：把醫師清單 + 症狀給 Gemini，根據 specialty_tags 選最適合的醫師"""
#     doctor_lines = []
#     for i, doc in enumerate(doctors):
#         line = f"{i+1}. {doc['name']}（{doc['title']}）"
#         if doc["specialty_tags"]:
#             line += f" 專長：{doc['specialty_tags']}"
#         doctor_lines.append(line)
#     doctor_list_str = "\n".join(doctor_lines)
#
#     prompt = f"""以下是醫師清單：
# {doctor_list_str}
#
# 病患症狀：{symptom}
#
# 請從以上醫師中選出最適合的一位，輸出以下 JSON，不要輸出任何其他文字：
# {{
#   "doctor_name": "醫師姓名（必須完全符合上面清單的名字）"
# }}"""
#
#     llm = Settings.llm
#     response = str(llm.complete(prompt)).replace("```json", "").replace("```", "").strip()
#     try:
#         result = json.loads(response)
#         selected_name = result.get("doctor_name", "")
#         for doc in doctors:
#             if doc["name"] == selected_name:
#                 return doc
#     except json.JSONDecodeError:
#         pass
#     return doctors[0]


# def get_schedule_from_db(doctor_name):
#     """段四：查詢醫師最近的看診班表，回傳日期和診別"""
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     today = datetime.today().date()
#     today_dow = today.weekday()
#
#     cursor.execute("""
#         SELECT
#             s.day_of_week,
#             CASE s.session
#                 WHEN 0 THEN '早診'
#                 WHEN 1 THEN '午診'
#                 WHEN 2 THEN '晚診'
#                 ELSE '門診'
#             END AS session_name
#         FROM Schedule s
#         JOIN Doctor d ON s.doctor_id = d.doctor_id
#         WHERE d.name = ?
#           AND s.is_active = 1
#           AND d.is_active = 1
#         ORDER BY s.day_of_week, s.session
#     """, doctor_name)
#
#     rows = cursor.fetchall()
#     conn.close()
#
#     if not rows:
#         return {"date": "", "session": ""}
#
#     best_date = None
#     best_session = ""
#     for row in rows:
#         target_dow = int(row[0])
#         days_ahead = (target_dow - today_dow) % 7
#         if days_ahead == 0:
#             days_ahead = 7
#         candidate_date = today + timedelta(days=days_ahead)
#         if best_date is None or candidate_date < best_date:
#             best_date = candidate_date
#             best_session = row[1]
#
#     return {"date": str(best_date), "session": best_session}

