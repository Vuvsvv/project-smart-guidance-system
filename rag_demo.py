import json
import os
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
# 3. 載入「有醫師的科別」清單（快取）
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
        print(f"科別清單載入完成（共 {len(_dept_list_cache)} 個科別）：")
        for dept in _dept_list_cache:
            print(f"  - {dept}")
        return _dept_list_cache
    except Exception as e:
        print(f"載入科別失敗：{e}")
        return []

# ─────────────────────────────────────────
# 4. 判斷科別
#    把「有醫師的科別清單」+ 問題 一起丟給 AI
#    AI 直接從清單裡選，不用模糊比對
#    這樣回傳的科別名稱一定是資料庫裡有的
# ─────────────────────────────────────────
def identify_department(symptom: str) -> dict:
    dept_list = get_active_dept_names()
    dept_list_str = "\n".join([f"- {d}" for d in dept_list])

    prompt = f"""你是台北榮民總醫院的分診助理。

以下是本院目前可掛號的科別清單：
{dept_list_str}

病患描述：{symptom}

請從上方科別清單中選出最適合的一個，並輸出以下 JSON，不要輸出任何其他文字：
{{
  "dept_name": "從清單中選出的科別名稱（必須完全一樣，不能自己改）",
  "urgency": "high 或 low（high 只用在：昏迷、大量出血、呼吸困難、心跳停止）",
  "reason": "一句話說明為什麼選這個科別"
}}"""

    llm = Settings.llm
    response = str(llm.complete(prompt)).strip().replace("```json", "").replace("```", "").strip()
    print(f"  → AI 回答：{response}")

    try:
        result = json.loads(response)
        dept_name = result.get("dept_name", "")
        urgency = result.get("urgency", "low")
        reason = result.get("reason", "")

        # 確認 AI 選的科別真的在清單裡（防止 AI 亂改名稱）
        if dept_name not in dept_list:
            print(f"  ⚠️ AI 選的科別「{dept_name}」不在清單裡，嘗試模糊比對...")
            matched = [d for d in dept_list if dept_name in d or d in dept_name]
            if matched:
                dept_name = matched[0]
                print(f"  → 修正為：{dept_name}")
            else:
                dept_name = ""

        return {"dept_name": dept_name, "urgency": urgency, "reason": reason}

    except json.JSONDecodeError:
        print(f"  ⚠️ JSON 解析失敗")
        return {"dept_name": "", "urgency": "low", "reason": ""}

# ─────────────────────────────────────────
# 5. 主要查詢流程
# ─────────────────────────────────────────
def process_query(user_input: str) -> dict:
    print("  判斷科別中...")
    dept_result = identify_department(user_input)
    dept_name = dept_result.get("dept_name", "")
    urgency = dept_result.get("urgency", "low")
    reason = dept_result.get("reason", "")
    print(f"  → 科別：{dept_name}，緊急：{urgency}，原因：{reason}")

    # 急症
    if urgency == "high":
        return {
            "isSuccess": True,
            "data": {
                "department_parent": "",
                "department_child": "急診",
                "doctor": "",
                "date": "", "session": "", "urgency": "high"
            },
            "script": ["行動掛號", "繼續掛號", "急診", "填寫個人資料"],
            "message": "請立即前往急診或撥打 119"
        }

    # 找不到科別
    if not dept_name:
        return {
            "isSuccess": False,
            "data": {
                "department_parent": "", "department_child": "",
                "doctor": "", "date": "", "session": "", "urgency": "low"
            },
            "script": [],
            "message": "無法判斷科別，請向櫃台詢問"
        }

    # 科別判斷成功
    return {
        "isSuccess": True,
        "data": {
            "department_parent": "",    # 待補
            "department_child": dept_name,
            "doctor": "",               # 待補
            "date": "",                 # 待補
            "session": "",              # 待補
            "urgency": urgency
        },
        "script": [
            "行動掛號",
            "繼續掛號",
            "依門診科別",
            dept_name,
            "選擇看診時間"
            # 待補：日期、醫師姓名、填寫個人資料
        ],
        "message": f"AI 建議：{dept_name}\n原因：{reason}"
    }

# ─────────────────────────────────────────
# 6. 主程式
# ─────────────────────────────────────────
def main():
    print("=" * 50)
    print("  台北榮民醫院導引系統（科別判斷版）")
    print("=" * 50)

    get_active_dept_names()

    print("\n進入互動模式（輸入 q 結束）\n")
    while True:
        user_input = input("請輸入您的問題：").strip()
        if user_input.lower() == "q":
            break
        if not user_input:
            continue
        result = process_query(user_input)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()


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
#     today_dow = today.weekday()  # 0=週一...6=週日
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
#     # 找最近的看診日
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


# ── 接上醫師和班表後，process_query 裡補上這段 ──────────────
#
#     # 段二：查詢醫師
#     doctors = get_doctors_by_dept(dept_name)
#     if not doctors:
#         return {"isSuccess": False, ...}
#
#     # 段三：選最適合醫師
#     best_doctor = pick_best_doctor(user_input, doctors)
#     doctor_name = best_doctor["name"]
#     actual_dept = best_doctor["dept_name"]
#
#     # 段四：查班表
#     schedule = get_schedule_from_db(doctor_name)
#     date_str = schedule.get("date", "")
#     session_str = schedule.get("session", "")
#
#     # script 補上醫師和日期
#     day_label = date_str.split("-")[-1] + "日" if date_str else ""
#     script = ["行動掛號", "繼續掛號", "依門診科別", actual_dept, "選擇看診時間"]
#     if day_label:
#         script.append(day_label)
#     script.append(doctor_name)
#     script.append("填寫個人資料")

