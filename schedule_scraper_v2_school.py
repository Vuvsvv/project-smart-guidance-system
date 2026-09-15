#!/usr/bin/env python3
"""
台北榮總複診班表爬蟲（手機 API 版）
使用手機版 API 抓取班表資料，寫進 MediChainDB 的 Schedule table

使用方式：
    python schedule_scraper_v2_school.py
    python schedule_scraper_v2_school.py --no-db    # 只抓不寫入DB
    python schedule_scraper_v2_school.py --delay 0.2
"""

import time
import argparse
import logging
from datetime import datetime

import pyodbc
from curl_cffi import requests

# ─── Config ───────────────────────────────────────────────────────────────────
MOBILE_BASE  = "https://m.vghtpe.gov.tw:6443/MobileWeb"
SECT_URL     = f"{MOBILE_BASE}/sectclassJSON"
SCHED_URL    = f"{MOBILE_BASE}/register/regfindsect"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
}

import os

DB_CONFIG = {
    "server":   os.environ.get("MEDICHAIN_DB_SERVER", "100.64.116.35,1433"),
    "database": os.environ.get("MEDICHAIN_DB_NAME", "MediChainDB"),
    "username": os.environ.get("MEDICHAIN_DB_USER", "sa"),
    "password": os.environ.get("MEDICHAIN_DB_PASSWORD"),
}

DEPT_ALIAS = {
    "外傷兼疝氣及肝膽胰胃腸外科": "外傷兼疝氣及肝膽胃腸外科",
    "旅遊諮詢門診(含留學體檢/疫苗)": "旅遊諮詢門診",
    "整形外科(眼整形及鼻整形特別門診)": "整形外科(眼整形及顎顏面整形特別門診)",
}

STATUS_MAP = {
    "Y": None,
    "V": "額滿",
    "E": "額滿關診",
    "F": "請假休診",
    "A": "已逾掛號時間",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def get_conn():
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']};"
        "TrustServerCertificate=yes;Encrypt=no;"
    )


def fetch_sect_list():
    r = requests.get(SECT_URL, headers=HEADERS, impersonate="chrome", timeout=15)
    r.raise_for_status()
    data = r.json()
    result = []
    for cat in data.get("RECORDS", []):
        classname = cat["classname"]
        for sect in cat.get("RECORDS", []):
            result.append((classname, sect["sectname"], sect["sectids"]))
    return result


def fetch_schedule(sectids):
    body = "&".join([f"sect={s}" for s in sectids])
    r = requests.post(SCHED_URL, data=body, headers=HEADERS, impersonate="chrome", timeout=15)
    r.raise_for_status()
    return [l.strip() for l in r.text.strip().split("\n") if l.strip()]


def parse_session(code):
    """
    根據 API 第 2 欄代碼判斷時段
    A: 上午 (早上)
    P: 下午
    N: 夜診
    """
    code = code.strip().upper()
    if code == "P":
        return "下午"
    elif code == "N":
        return "夜診"
    elif code == "A":
        return "早上"
    return "早上"


def parse_date(raw):
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return None


def parse_lines(lines, sectname):
    dept_name = DEPT_ALIAS.get(sectname, sectname)
    today = datetime.now().strftime("%Y-%m-%d")
    records = []
    for line in lines:
        parts = line.split(",")
        if len(parts) < 9:
            continue
        date_str = parse_date(parts[0].strip())
        if not date_str or date_str < today:
            continue
        records.append({
            "date":       date_str,
            "session":    parse_session(parts[1]),  # 改為傳入第 2 欄時段代碼 (A/P/N)
            "room":       parts[3].strip(),
            "doc_id":     parts[4].strip(),
            "doc_name":   parts[5].strip(),
            "dept_name":  dept_name,
            "detail_tag": None,
            "status":     STATUS_MAP.get(parts[8].strip(), None),
            "visit_type": "複診",
        })
    return records


def upsert_schedule(records, visit_type="複診"):
    conn   = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT doctor_id, vgh_code FROM Doctor")
    doc_map = {row[1]: row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT dept_id, name FROM Department")
    dept_map = {row[1]: row[0] for row in cursor.fetchall()}

    cursor.execute(
        "DELETE FROM Schedule WHERE date < CAST(GETDATE() AS DATE) AND visit_type = ?",
        visit_type
    )
    conn.commit()
    log.info("已清除過期班表（%s）", visit_type)

    valid, skipped = [], 0
    for r in records:
        doc_id  = doc_map.get(r["doc_id"])
        dept_id = dept_map.get(r["dept_name"])
        if not doc_id or not dept_id:
            skipped += 1
            continue
        valid.append((
            doc_id, dept_id,
            r["date"], r["session"], r["room"],
            r["detail_tag"], r["status"], visit_type
        ))

    inserted = 0
    for i in range(0, len(valid), 500):
        batch = valid[i:i+500]
        cursor.executemany("""
            MERGE Schedule AS target
            USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?)) AS source
                (doctor_id, dept_id, date, session, room, detail_tag, status, visit_type)
            ON target.doctor_id   = source.doctor_id
               AND target.date    = source.date
               AND target.session = source.session
               AND target.room    = source.room
               AND target.visit_type = source.visit_type
            WHEN MATCHED THEN
                UPDATE SET dept_id    = source.dept_id,
                           detail_tag = source.detail_tag,
                           status     = source.status,
                           updated_at = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (doctor_id, dept_id, date, session, room, detail_tag, status, visit_type, updated_at)
                VALUES (source.doctor_id, source.dept_id, source.date, source.session,
                        source.room, source.detail_tag, source.status, source.visit_type, GETDATE());
        """, batch)
        inserted += len(batch)
        log.info("  已寫入 %d / %d 筆", inserted, len(valid))

    conn.commit()
    cursor.close()
    conn.close()
    return inserted, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-db", action="store_true", help="只抓不寫入DB")
    parser.add_argument("--delay", type=float, default=0.2, help="請求間隔秒數")
    args = parser.parse_args()

    log.info("抓取複診科別列表...")
    sects = fetch_sect_list()
    log.info("共 %d 個科別", len(sects))

    all_records = []
    for i, (classname, sectname, sectids) in enumerate(sects):
        log.info("[%d/%d] %s > %s", i+1, len(sects), classname, sectname)
        try:
            lines   = fetch_schedule(sectids)
            records = parse_lines(lines, sectname)
            all_records.extend(records)
            log.info("  找到 %d 筆", len(records))
        except Exception as e:
            log.error("  失敗: %s", e)
        time.sleep(args.delay)

    log.info("共 %d 筆班表記錄", len(all_records))

    if args.no_db:
        log.info("--no-db 模式，不寫入DB")
        for r in all_records[:5]:
            print(r)
        return

    log.info("寫入 MediChainDB...")
    inserted, skipped = upsert_schedule(all_records, visit_type="複診")
    log.info("完成：寫入 %d 筆，跳過 %d 筆", inserted, skipped)


if __name__ == "__main__":
    main()