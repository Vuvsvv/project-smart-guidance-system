"""
執行：python export_schedule.py
"""

import json
import os
import pyodbc
from datetime import date

import os

DB_CONFIG = {
    "server":   os.environ.get("MEDICHAIN_DB_SERVER", "100.64.116.35,1433"),
    "database": os.environ.get("MEDICHAIN_DB_NAME", "MediChainDB"),
    "username": os.environ.get("MEDICHAIN_DB_USER", "sa"),
    "password": os.environ.get("MEDICHAIN_DB_PASSWORD"),
}

def get_conn():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)

def main():
    print("連線 DB 中...")
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            doc.name        AS doctor,
            dc.name         AS category,
            d.name          AS department,
            s.date          AS date,
            s.session       AS session,
            s.room          AS room,
            s.visit_type    AS visit_type,
            s.status        AS status
        FROM Schedule s
        JOIN Doctor doc             ON doc.doctor_id  = s.doctor_id
        JOIN Department d           ON d.dept_id      = s.dept_id
        JOIN DepartmentCategory dc  ON dc.category_id = d.category_id
        WHERE s.date >= CAST(GETDATE() AS DATE)
        ORDER BY s.date, d.name, s.session, doc.name
    """)

    rows = []
    for row in cursor.fetchall():
        rows.append({
            "doctor":     row.doctor,
            "category":   row.category,
            "department": row.department,
            "date":       str(row.date),
            "session":    row.session,
            "room":       row.room,
            "visit_type": row.visit_type,
            "status":     row.status,
        })

    cursor.close()
    conn.close()

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    out_path = os.path.join(desktop, "schedule.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"完成！共 {len(rows)} 筆，已輸出至 {out_path}")

if __name__ == "__main__":
    main()
