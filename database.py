import os
import pyodbc
from dotenv import load_dotenv  
load_dotenv()                   

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


_dept_with_category_cache = None

def get_departments_with_category() -> list[dict]:
    """
    撈「父科別 + 子科別 + dept_id」。
    給資料流2 第三步當 AI 候選名單、第八步組 fallback（找同父科別兄弟科）用。
    回傳 [{"parentDept": ..., "childDept": ..., "dept_id": ..., "category_id": ...}, ...]
    """
    global _dept_with_category_cache
    if _dept_with_category_cache is not None:
        return _dept_with_category_cache
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dc.category_id, dc.name AS parent, d.dept_id, d.name AS child
            FROM DepartmentCategory dc
            JOIN Department d ON d.category_id = dc.category_id
            ORDER BY dc.name, d.name
        """)
        rows = cursor.fetchall()
        conn.close()
        _dept_with_category_cache = [{
            "category_id": row[0],
            "parentDept": row[1],
            "dept_id": row[2],
            "childDept": row[3],
        } for row in rows]
        print(f"科別清單（含父科別）載入完成（共 {len(_dept_with_category_cache)} 個子科別）")
        return _dept_with_category_cache
    except Exception as e:
        print(f"載入科別（含父科別）失敗：{e}")
        return []


def get_available_schedules(dept_name: str, from_date: str) -> list[dict]:
    """
    查某子科別從 from_date（含）起、可掛號的真實醫師班表（全部時段）。
      - status IS NULL      → 可掛號
      - is_placeholder = 0  → 只取真實醫師
    時段/星期的篩選改由 recommend.py 用 available_slots 組合在 Python 端做。
    回傳 [{"doctor", "childDept", "date", "session", "room", "detail_tag"}, ...]
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
            SELECT doc.name, d.name, s.date, s.session, s.room, s.detail_tag
            FROM Schedule s
            JOIN Doctor doc ON doc.doctor_id = s.doctor_id
            JOIN Department d ON d.dept_id = s.dept_id
            WHERE d.name = ?
              AND s.date >= ?
              AND s.status IS NULL
              AND doc.is_placeholder = 0
            ORDER BY s.date, s.session
        """
        cursor.execute(sql, dept_name, from_date)
        rows = cursor.fetchall()
        conn.close()
        return [{
            "doctor": row[0],
            "childDept": row[1],
            "date": str(row[2]),
            "session": row[3],
            "room": row[4],
            "detail_tag": row[5] or "",
        } for row in rows]
    except Exception as e:
        print(f"查詢班表失敗：{e}")
        return []
