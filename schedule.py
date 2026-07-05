from datetime import datetime, timedelta

TODAY = datetime.today().strftime("%Y-%m-%d")

_WEEKDAY_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]

SESSION_TIMES = {
    "早上": ("08:30", "12:00"),
    "下午": ("13:30", "17:00"),
    "夜診": ("18:00", "21:00"),
}
CUTOFF_BUFFER_MIN = 30  


def _session_range(session: str) -> str:
    start, end = SESSION_TIMES.get(session, (None, None))
    return f"{start}-{end}" if start else ""

SESSIONS_DESC = " / ".join(f"{s}（{_session_range(s)}）" for s in ("早上", "下午", "夜診"))


def _session_open(row: dict, now: datetime = None) -> bool:
    now = now or datetime.now()
    if row["date"] != now.strftime("%Y-%m-%d"):
        return True
    end = SESSION_TIMES.get(row["session"], (None, None))[1]
    if not end:
        return True
    cutoff = datetime.strptime(f"{row['date']} {end}", "%Y-%m-%d %H:%M") \
        - timedelta(minutes=CUTOFF_BUFFER_MIN)
    return now <= cutoff


def _weekday_zh(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return _WEEKDAY_ZH[d.weekday()]
    except ValueError:
        return ""


def _slot_match(row: dict, slots: list) -> bool:
    if not slots:
        return True
    day = _weekday_zh(row["date"])
    return any(s.day == day and s.session == row["session"] for s in slots)


def select_feasible(all_rows, slots, doctor_pref):
    has_doctor = bool(doctor_pref and doctor_pref != "不限")
    doc_rows = [r for r in all_rows if doctor_pref in r["doctor"]] if has_doctor else all_rows

    feasible = [r for r in doc_rows if _slot_match(r, slots)]
    relaxed_by_date = False

    if not feasible and has_doctor:            
        feasible = [r for r in all_rows if _slot_match(r, slots)]

    if not feasible:                             #
        feasible = doc_rows if (has_doctor and doc_rows) else all_rows
        relaxed_by_date = True

    return feasible, relaxed_by_date
