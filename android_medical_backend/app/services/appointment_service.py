from __future__ import annotations

from app.db import fetch_active_departments, fetch_available_slots, fetch_mock_slots, parent_department_for
from app.schemas import (
    DepartmentResult,
    FallbackDepartment,
    RecommendationColumns,
    RecommendationItem,
    RecommendationResult,
    TriageCase,
)
from app.services.rag_triage_adapter import detect_department_with_ai


async def detect_department_result(case: TriageCase) -> DepartmentResult:
    departments = fetch_active_departments()
    child_names = [item["child_dept"] for item in departments if item["child_dept"]]
    if not child_names:
        return _rule_based_department(case, [])

    result = await detect_department_with_ai(case, departments)
    if result and result.childDept in child_names:
        return result
    return _rule_based_department(case, departments)


async def recommend_appointments(case: TriageCase) -> RecommendationResult:
    department = case.department_result or await detect_department_result(case)
    case.department_result = department

    preferred_days = case.availability.preferred_days
    preferred_sessions = case.availability.preferred_sessions

    primary_slots = fetch_available_slots(department.childDept, search_days=21, max_slots=10)
    fallback_departments = _fallback_departments_for(department.childDept)

    slots = primary_slots
    if not slots:
        for fallback in fallback_departments:
            slots = fetch_available_slots(fallback.childDept, search_days=21, max_slots=10)
            if slots:
                break

    if not slots:
        slots = fetch_available_slots("一般骨科", search_days=21, max_slots=10)
    if not slots:
        slots = fetch_mock_slots(department.childDept, search_days=21, max_slots=10)
    if not slots:
        slots = fetch_mock_slots("一般骨科", search_days=21, max_slots=10)

    specialty_first = _build_recommendations(
        case_id=case.case_id,
        slots=slots,
        prefix="rec_s",
        preferred_days=preferred_days,
        preferred_sessions=preferred_sessions,
        specialty_first=True,
    )
    time_first = _build_recommendations(
        case_id=case.case_id,
        slots=slots,
        prefix="rec_t",
        preferred_days=preferred_days,
        preferred_sessions=preferred_sessions,
        specialty_first=False,
    )

    total_count = len(specialty_first[:5]) + len(time_first[:5])
    return RecommendationResult(
        case_id=case.case_id,
        recommendations=RecommendationColumns(
            specialty_first=specialty_first[:5],
            time_first=time_first[:5],
        ),
        fallback_departments=fallback_departments,
        total_count=total_count,
    )


def _rule_based_department(case: TriageCase, departments: list[dict]) -> DepartmentResult:
    text = _case_text(case)
    candidates = [
        (["膝", "關節", "骨", "走路", "爬樓梯"], "一般骨科", ["症狀位置偏向骨科或關節問題"]),
        (["胸痛", "心悸", "心臟"], "心臟內科", ["症狀和胸痛或心臟相關"]),
        (["咳", "發燒", "喉嚨", "感冒"], "一般內科", ["症狀可先由一般內科評估"]),
        (["眼", "視力"], "眼科", ["症狀和眼部相關"]),
        (["皮膚", "疹", "癢"], "皮膚科", ["症狀和皮膚相關"]),
    ]
    available = {item["child_dept"] for item in departments}
    for keywords, dept, reasons in candidates:
        if any(keyword in text for keyword in keywords) and (not available or dept in available):
            return DepartmentResult(
                parentDept=_parent_for(dept, departments) or parent_department_for(dept),
                childDept=dept,
                confidence=0.75,
                reason=reasons,
            )

    fallback = "一般內科"
    if available and fallback not in available:
        fallback = next(iter(available))
    return DepartmentResult(
        parentDept=_parent_for(fallback, departments) or parent_department_for(fallback),
        childDept=fallback,
        confidence=0.45,
        reason=["AI 無法穩定判斷時，先以可掛號的一般科別評估"],
    )


def _build_recommendations(
    case_id: str,
    slots: list[dict],
    prefix: str,
    preferred_days: list[str],
    preferred_sessions: list[str],
    specialty_first: bool,
) -> list[RecommendationItem]:
    sorted_slots = sorted(slots, key=lambda slot: (slot.get("date"), _session_rank(slot.get("session", ""))))
    items = []
    seen = set()
    for index, slot in enumerate(sorted_slots):
        key = (slot["parent_dept"], slot["child_dept"], slot["doctor"], slot["date"], slot["session"])
        if key in seen:
            continue
        seen.add(key)

        score = _score_slot(slot, index, preferred_days, preferred_sessions, specialty_first)
        reasons = ["專長最符合", "目前可掛號"] if specialty_first else ["時間最近", "等待較短"]
        if slot.get("source") == "mock":
            reasons.append("Azure SQL 查詢失敗或無資料，使用 mock 班表")

        item = RecommendationItem(
            recommendation_id=f"{prefix}_{case_id}_{len(items) + 1:03d}",
            parentDept=slot["parent_dept"],
            childDept=slot["child_dept"],
            doctor=slot["doctor"],
            date=_date_to_text(slot["date"]),
            session=str(slot["session"]),
            slot=str(slot.get("slot", "")),
            score=score,
            reasons=reasons,
            rank=len(items) + 1,
            is_best_match=specialty_first and len(items) == 0,
        )
        items.append(item)
        if len(items) >= 5:
            break
    return items


def _fallback_departments_for(child_dept: str) -> list[FallbackDepartment]:
    if child_dept in {"一般內科", "家庭醫學科(一般門診/戒菸)"}:
        return []
    return [
        FallbackDepartment(
            parentDept="一般內科",
            childDept="一般內科",
            reason="原科別可掛號名額不足時，先由一般內科初步評估",
        )
    ]


def _score_slot(
    slot: dict,
    index: int,
    preferred_days: list[str],
    preferred_sessions: list[str],
    specialty_first: bool,
) -> float:
    score = 95.0 if specialty_first else 88.0
    score -= index * 3
    session = str(slot.get("session", ""))
    if any(preferred in session for preferred in preferred_sessions):
        score += 4
    if preferred_days:
        weekday = _weekday_label(slot.get("date"))
        if weekday in preferred_days:
            score += 4
    return max(0.0, min(score, 100.0))


def _session_rank(session: str) -> int:
    if "上午" in session or "早" in session:
        return 0
    if "下午" in session or "午" in session:
        return 1
    if "夜" in session or "晚" in session:
        return 2
    return 3


def _date_to_text(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _weekday_label(value) -> str:
    labels = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    if hasattr(value, "weekday"):
        return labels[value.weekday()]
    return ""


def _case_text(case: TriageCase) -> str:
    patient = case.patient_input
    parts = [
        patient.symptom,
        patient.body_part or "",
        patient.duration or "",
        patient.severity or "",
        patient.onset or "",
        " ".join(patient.accompanying_symptoms),
        " ".join(patient.red_flags),
    ]
    return "；".join(part for part in parts if part)


def _parent_for(child: str, departments: list[dict]) -> str:
    for item in departments:
        if item["child_dept"] == child:
            return item["parent_dept"]
    return ""
