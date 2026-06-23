import json
from datetime import date, timedelta
from pathlib import Path
from typing import List
import pyodbc

from .config import get_settings

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEPARTMENT_FILES = ["Followup_visit.json", "Initial_diagnosis.json"]
WEEKDAY_INDEX = {
    "星期一": 0,
    "星期二": 1,
    "星期三": 2,
    "星期四": 3,
    "星期五": 4,
    "星期六": 5,
    "星期日": 6,
}


def create_db_connection():
    settings = get_settings()
    conn_str = (
        f"DRIVER={{{settings.db_driver}}};"
        f"SERVER={settings.db_server};"
        f"DATABASE={settings.db_name};"
        f"UID={settings.db_user};"
        f"PWD={settings.db_password};"
        "Encrypt=yes;"
    )
    return pyodbc.connect(conn_str)


def fetch_active_departments() -> List[dict]:
    try:
        conn = create_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ISNULL(p.dept_name, c.dept_name) AS parent_dept,
                c.dept_name AS child_dept
            FROM Department c
            LEFT JOIN Department p ON c.parent_dept_id = p.dept_id
            ORDER BY parent_dept, child_dept
        """)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"parent_dept": row[0] or "", "child_dept": row[1] or ""}
            for row in rows
            if row[1]
        ]
    except Exception:
        return load_mock_departments()


def load_mock_departments() -> List[dict]:
    departments = []
    seen = set()
    for file_name in DEPARTMENT_FILES:
        path = DATA_DIR / file_name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for parent, children in data.items():
            for child in children:
                key = (parent, child)
                if key in seen:
                    continue
                seen.add(key)
                departments.append({"parent_dept": parent, "child_dept": child})
    return departments


def fetch_available_slots(department_text: str, search_days: int = 14, max_slots: int = 10) -> List[dict]:
    try:
        slots = _fetch_available_slots_from_db(department_text, search_days, max_slots)
        if slots:
            return slots
    except Exception:
        pass
    return fetch_mock_slots(department_text, search_days, max_slots)


def _fetch_available_slots_from_db(department_text: str, search_days: int, max_slots: int) -> List[dict]:
    conn = create_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            p.dept_name AS parent_dept,
            c.dept_name AS child_dept,
            ISNULL(sub.name, d.name) AS doctor_name,
            s.session
        FROM Schedule s
        JOIN Doctor d ON s.doctor_id = d.doctor_id
        JOIN Department c ON s.dept_id = c.dept_id
        JOIN Department p ON c.parent_dept_id = p.dept_id
        LEFT JOIN LeaveSubstitute lv ON lv.doctor_id = d.doctor_id 
            AND lv.leave_date = ? AND lv.session = s.session
        LEFT JOIN Doctor sub ON lv.substitute_id = sub.doctor_id
        WHERE c.dept_name LIKE ?
            AND s.day_of_week = ?
            AND s.is_active = 1
            AND d.is_active = 1
            AND (lv.leave_id IS NULL OR lv.substitute_id IS NOT NULL)
        ORDER BY s.session ASC
    """

    slots = []
    for day_offset in range(1, search_days + 1):
        if len(slots) >= max_slots:
            break

        appointment_date = date.today() + timedelta(days=day_offset)
        sql_day_of_week = (appointment_date.weekday() + 1) % 7

        cursor.execute(query, appointment_date, f"%{department_text}%", sql_day_of_week)
        rows = cursor.fetchall()

        for row in rows:
            if len(slots) >= max_slots:
                break

            slots.append({
                "parent_dept": row[0],
                "child_dept": row[1],
                "doctor": row[2],
                "session": row[3],
                "date": appointment_date,
            })

    conn.close()
    return slots


def fetch_mock_slots(department_text: str, search_days: int = 14, max_slots: int = 10) -> List[dict]:
    path = DATA_DIR / "mock_schedule.json"
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    dept_key = _find_mock_department(data, department_text)
    if not dept_key:
        dept_key = next(iter(data.keys()), "")
    if not dept_key:
        return []

    parent = parent_department_for(dept_key)
    slots = []
    for doctor, sessions in data[dept_key].items():
        for raw_session in sessions:
            if len(slots) >= max_slots:
                return slots
            appointment_date, session = _mock_session_to_date(raw_session)
            slots.append({
                "parent_dept": parent,
                "child_dept": dept_key,
                "doctor": doctor,
                "session": session,
                "date": appointment_date,
                "slot": "3209診",
                "source": "mock",
            })
    return slots


def parent_department_for(child_dept: str) -> str:
    for item in load_mock_departments():
        if item["child_dept"] == child_dept:
            return item["parent_dept"]
    return ""


def _find_mock_department(data: dict, department_text: str) -> str:
    if department_text in data:
        return department_text
    for dept in data:
        if department_text in dept or dept in department_text:
            return dept
    return ""


def _mock_session_to_date(raw_session: str) -> tuple[date, str]:
    target_weekday = None
    session = raw_session
    for weekday, index in WEEKDAY_INDEX.items():
        if raw_session.startswith(weekday):
            target_weekday = index
            session = raw_session.replace(weekday, "", 1) or "上午"
            break

    today = date.today()
    if target_weekday is None:
        return today + timedelta(days=1), session

    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead), session
