from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas import SemanticExtraction, SeverityNormalization, UrgencyNormalization
from app.services.confidence_scoring import (
    accepted,
    clamp_confidence,
    confidence_with_uncertainty,
    needs_clarification,
)

PREFERRED_DAYS_KEY = "preferred_days"
PREFERRED_SESSIONS_KEY = "preferred_sessions"

ALL_WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
WEEKDAY_DAYS = ["週一", "週二", "週三", "週四", "週五"]
WEEKEND_DAYS = ["週六", "週日"]
ALL_SESSIONS = ["上午", "下午", "夜間"]

ANY_TIME_TERMS = ["都可以", "都有空", "皆可", "隨時", "任何", "都方便", "都行"]
NO_WORK_TERMS = ["沒上班", "不用上班", "沒有上班", "最近沒上班", "近期沒上班"]
UNKNOWN_TERMS = ["不知道", "不確定", "再看看", "看看", "不清楚", "還不確定", "之後再說"]
UNAVAILABLE_TERMS = ["沒空", "不能", "不行", "不方便", "無法", "沒辦法"]

RED_FLAG_BUCKETS = {
    "突發胸痛": ["突發胸痛", "劇烈胸痛", "胸痛", "胸悶冒冷汗", "痛到冒冷汗"],
    "嚴重呼吸困難": ["呼吸困難", "喘不過氣", "無法呼吸", "有點喘"],
    "中風徵象": ["嘴歪", "半邊無力", "說話不清", "中風"],
    "大量出血": ["大量出血", "血流不止"],
    "意識異常": ["昏倒", "快昏倒", "昏迷", "意識不清", "叫不醒"],
    "劇烈頭痛合併神經症狀": ["劇烈頭痛", "視力模糊", "抽搐"],
    "持續高燒": ["持續高燒", "高燒不退"],
}

NEGATION_TERMS = ["沒有", "無", "否認", "都沒有", "沒這些", "不會", "沒有以上"]


@dataclass
class NormalizationResult:
    extractions: list[SemanticExtraction] = field(default_factory=list)
    severity: SeverityNormalization | None = None
    urgency: UrgencyNormalization | None = None


def normalize_message(text: str, last_question_key: str | None = None) -> NormalizationResult:
    result = NormalizationResult()
    result.extractions.extend(_normalize_availability(text, last_question_key))

    severity = normalize_severity(text)
    if severity.semantic_status != "unknown" or last_question_key == "severity":
        result.severity = severity
        result.extractions.append(
            _extraction(
                field="severity",
                normalized_value={
                    "severity_level": severity.severity_level,
                    "functional_impact": severity.functional_impact,
                    "sleep_impact": severity.sleep_impact,
                },
                semantic_status=severity.semantic_status,
                confidence=severity.confidence,
                source_text=text,
                follow_up_reason=severity.follow_up_reason,
            )
        )

    urgency = normalize_urgency(text, last_question_key)
    result.urgency = urgency
    if urgency.semantic_status != "unknown" or last_question_key == "red_flags":
        result.extractions.append(
            _extraction(
                field="red_flags",
                normalized_value=urgency.matched_red_flags,
                semantic_status=urgency.semantic_status,
                confidence=urgency.confidence,
                source_text=text,
                follow_up_reason=urgency.follow_up_reason,
            )
        )

    return result


def normalize_severity(text: str) -> SeverityNormalization:
    sleep_impact = any(term in text for term in ["睡不著", "睡不好", "痛醒", "不能睡"])
    severe_impact = any(term in text for term in ["快受不了", "受不了", "無法工作", "不能工作", "無法走路", "痛到冒冷汗"])
    functional_impact = severe_impact or any(term in text for term in ["影響生活", "走路困難", "爬樓梯很吃力", "不能活動"])
    mild_terms = ["有點痛", "一點痛", "微痛", "有點不舒服", "還好", "還能工作", "輕微"]
    moderate_terms = ["普通", "中等", "明顯", "不舒服", "痠痛", "會痛"]
    severe_terms = ["很痛", "劇痛", "嚴重", "快受不了", "受不了", "痛到睡不著", "痛到冒冷汗"]

    if sleep_impact or severe_impact or any(term in text for term in severe_terms):
        confidence = 0.92 if sleep_impact or severe_impact else 0.84
        return SeverityNormalization(
            severity_level="severe",
            functional_impact=functional_impact,
            sleep_impact=sleep_impact,
            confidence=confidence,
            semantic_status="available",
            source_text=text,
        )

    if any(term in text for term in mild_terms):
        confidence = confidence_with_uncertainty(0.78, text)
        return SeverityNormalization(
            severity_level="mild",
            functional_impact=False if "還能工作" in text else functional_impact,
            sleep_impact=False,
            confidence=confidence,
            semantic_status="available" if accepted(confidence, "available") else "ambiguous",
            source_text=text,
            needs_clarification=needs_clarification(confidence, "available"),
            follow_up_reason="severity confidence below threshold" if confidence < 0.55 else None,
        )

    if any(term in text for term in moderate_terms):
        confidence = confidence_with_uncertainty(0.72, text)
        return SeverityNormalization(
            severity_level="moderate",
            functional_impact=functional_impact,
            sleep_impact=False,
            confidence=confidence,
            semantic_status="available" if accepted(confidence, "available") else "ambiguous",
            source_text=text,
            needs_clarification=needs_clarification(confidence, "available"),
            follow_up_reason="severity confidence below threshold" if confidence < 0.55 else None,
        )

    if any(term in text for term in UNKNOWN_TERMS):
        return SeverityNormalization(
            confidence=0.2,
            semantic_status="unknown",
            source_text=text,
            needs_clarification=True,
            follow_up_reason="使用者無法判斷嚴重程度",
        )

    if any(term in text for term in ["吧", "好像", "可能", "應該"]):
        return SeverityNormalization(
            severity_level=None,
            confidence=0.42,
            semantic_status="ambiguous",
            source_text=text,
            needs_clarification=True,
            follow_up_reason="嚴重程度語意模糊",
        )

    return SeverityNormalization(source_text=text)


def normalize_urgency(text: str, last_question_key: str | None = None) -> UrgencyNormalization:
    matched: list[str] = []
    for label, terms in RED_FLAG_BUCKETS.items():
        if any(term in text and not _is_negated(text, term) for term in terms):
            matched.append(label)

    if matched:
        level = "high" if any(flag in matched for flag in ["突發胸痛", "嚴重呼吸困難", "中風徵象", "大量出血", "意識異常"]) else "medium"
        confidence = 0.9 if level == "high" else 0.76
        return UrgencyNormalization(
            urgency_level=level,
            matched_red_flags=list(dict.fromkeys(matched)),
            confidence=confidence,
            warning_required=level == "high",
            semantic_status="available",
            source_text=text,
        )

    if _has_negation(text) and (_mentions_red_flag(text) or last_question_key == "red_flags"):
        return UrgencyNormalization(
            urgency_level="low",
            matched_red_flags=[],
            confidence=0.9,
            warning_required=False,
            semantic_status="unavailable",
            source_text=text,
        )

    if any(term in text for term in UNKNOWN_TERMS) and last_question_key == "red_flags":
        return UrgencyNormalization(
            urgency_level="low",
            matched_red_flags=[],
            confidence=0.25,
            warning_required=False,
            semantic_status="unknown",
            source_text=text,
            needs_clarification=True,
            follow_up_reason="使用者無法確認紅旗症狀",
        )

    return UrgencyNormalization(source_text=text)


def _normalize_availability(text: str, last_question_key: str | None) -> list[SemanticExtraction]:
    extractions: list[SemanticExtraction] = []
    days = normalize_preferred_days(text, last_question_key)
    if days is not None:
        extractions.append(days)

    sessions = normalize_preferred_sessions(text, last_question_key)
    if sessions is not None:
        extractions.append(sessions)

    leave = normalize_can_take_leave(text)
    if leave is not None:
        extractions.append(leave)

    return extractions


def normalize_preferred_days(text: str, last_question_key: str | None = None) -> SemanticExtraction | None:
    normalized = _normalize_weekday_text(text)

    if _is_unknown_answer(normalized, last_question_key, PREFERRED_DAYS_KEY):
        return _extraction(PREFERRED_DAYS_KEY, [], "unknown", 0.2, text, "日期偏好不確定")
    if _is_unavailable_answer(normalized, last_question_key, PREFERRED_DAYS_KEY):
        return _extraction(PREFERRED_DAYS_KEY, [], "unavailable", 0.82, text, "使用者表示最近沒有可就醫日期")

    days: list[str] = []
    confidence = 0.0
    if _is_any_days_answer(normalized, last_question_key):
        days.extend(ALL_WEEKDAYS)
        confidence = confidence_with_uncertainty(0.8, normalized)

    if last_question_key == PREFERRED_DAYS_KEY and any(term in normalized for term in NO_WORK_TERMS):
        days.extend(ALL_WEEKDAYS)
        confidence = max(confidence, confidence_with_uncertainty(0.72, normalized))

    if any(term in normalized for term in ["週一到週五", "週一至週五", "週一-週五", "平日", "工作日", "週間"]):
        days.extend(WEEKDAY_DAYS)
        confidence = max(confidence, confidence_with_uncertainty(0.88, normalized))

    if any(term in normalized for term in ["週末", "假日", "六日", "週六日", "週六週日"]):
        days.extend(WEEKEND_DAYS)
        confidence = max(confidence, confidence_with_uncertainty(0.86, normalized))

    range_match = re.search(r"週([一二三四五六日])\s*(?:到|至|-|～|~)\s*週([一二三四五六日])", normalized)
    if range_match:
        days.extend(_weekday_range(f"週{range_match.group(1)}", f"週{range_match.group(2)}"))
        confidence = max(confidence, confidence_with_uncertainty(0.9, normalized))

    for day in ALL_WEEKDAYS:
        if day in normalized:
            days.append(day)
            confidence = max(confidence, confidence_with_uncertainty(0.9, normalized))

    if not days:
        if last_question_key == PREFERRED_DAYS_KEY and any(term in normalized for term in ["吧", "可能", "應該"]):
            return _extraction(PREFERRED_DAYS_KEY, [], "ambiguous", 0.42, text, "日期偏好語意模糊")
        return None

    status = "available" if len(set(days)) == len(ALL_WEEKDAYS) else "partial"
    return _extraction(PREFERRED_DAYS_KEY, _unique(days), status, confidence, text)


def normalize_preferred_sessions(text: str, last_question_key: str | None = None) -> SemanticExtraction | None:
    if _is_unknown_answer(text, last_question_key, PREFERRED_SESSIONS_KEY):
        return _extraction(PREFERRED_SESSIONS_KEY, [], "unknown", 0.2, text, "看診時段不確定")
    if _is_unavailable_answer(text, last_question_key, PREFERRED_SESSIONS_KEY):
        return _extraction(PREFERRED_SESSIONS_KEY, [], "unavailable", 0.75, text, "使用者表示時段不方便")

    sessions: list[str] = []
    confidence = 0.0
    if last_question_key == PREFERRED_SESSIONS_KEY and any(term in text for term in ANY_TIME_TERMS):
        sessions.extend(ALL_SESSIONS)
        confidence = confidence_with_uncertainty(0.78, text)

    if last_question_key == PREFERRED_SESSIONS_KEY and any(term in text for term in NO_WORK_TERMS):
        sessions.extend(ALL_SESSIONS)
        confidence = max(confidence, confidence_with_uncertainty(0.72, text))

    if any(term in text for term in ["上午", "早上", "早晨", "一早", "中午前"]):
        sessions.append("上午")
        confidence = max(confidence, confidence_with_uncertainty(0.86, text))
    if any(term in text for term in ["下午", "午後", "中午後"]):
        sessions.append("下午")
        confidence = max(confidence, confidence_with_uncertainty(0.86, text))
    if any(term in text for term in ["夜間", "晚上", "晚間", "夜診", "下班後"]):
        sessions.append("夜間")
        confidence = max(confidence, confidence_with_uncertainty(0.86, text))
    if any(term in text for term in ["全天", "整天", "任何時段"]):
        sessions.extend(ALL_SESSIONS)
        confidence = max(confidence, confidence_with_uncertainty(0.88, text))

    if not sessions:
        return None

    status = "available" if len(set(sessions)) == len(ALL_SESSIONS) else "partial"
    return _extraction(PREFERRED_SESSIONS_KEY, _unique(sessions), status, confidence, text)


def normalize_can_take_leave(text: str) -> SemanticExtraction | None:
    if "請假" not in text:
        return None
    if any(term in text for term in ["不能", "不行", "不方便", "沒辦法", "無法", "不太方便"]):
        return _extraction("can_take_leave", False, "unavailable", 0.84, text)
    if any(term in text for term in ["可以", "能", "可", "願意"]):
        return _extraction("can_take_leave", True, "available", 0.86, text)
    return _extraction("can_take_leave", None, "ambiguous", 0.45, text, "請假意願不明確")


def _extraction(
    field: str,
    normalized_value: Any,
    semantic_status: str,
    confidence: float,
    source_text: str,
    follow_up_reason: str | None = None,
) -> SemanticExtraction:
    confidence = clamp_confidence(confidence)
    return SemanticExtraction(
        field=field,
        normalized_value=normalized_value,
        semantic_status=semantic_status,
        confidence=confidence,
        source_text=source_text,
        needs_clarification=needs_clarification(confidence, semantic_status),
        follow_up_reason=follow_up_reason,
    )


def _normalize_weekday_text(text: str) -> str:
    normalized = text
    replacements = {
        "星期一": "週一",
        "星期二": "週二",
        "星期三": "週三",
        "星期四": "週四",
        "星期五": "週五",
        "星期六": "週六",
        "星期日": "週日",
        "星期天": "週日",
        "禮拜一": "週一",
        "禮拜二": "週二",
        "禮拜三": "週三",
        "禮拜四": "週四",
        "禮拜五": "週五",
        "禮拜六": "週六",
        "禮拜日": "週日",
        "禮拜天": "週日",
        "周一": "週一",
        "周二": "週二",
        "周三": "週三",
        "周四": "週四",
        "周五": "週五",
        "周六": "週六",
        "周日": "週日",
        "周天": "週日",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _is_any_days_answer(text: str, last_question_key: str | None) -> bool:
    if any(term in text for term in ["每天", "整週", "全週", "這幾天都有空", "最近都有空"]):
        return True
    return last_question_key == PREFERRED_DAYS_KEY and any(term in text for term in ANY_TIME_TERMS)


def _is_unknown_answer(text: str, last_question_key: str | None, field: str) -> bool:
    return last_question_key == field and any(term in text for term in UNKNOWN_TERMS)


def _is_unavailable_answer(text: str, last_question_key: str | None, field: str) -> bool:
    return last_question_key == field and any(term in text for term in UNAVAILABLE_TERMS)


def _weekday_range(start: str, end: str) -> list[str]:
    if start not in ALL_WEEKDAYS or end not in ALL_WEEKDAYS:
        return []
    start_index = ALL_WEEKDAYS.index(start)
    end_index = ALL_WEEKDAYS.index(end)
    if start_index <= end_index:
        return ALL_WEEKDAYS[start_index : end_index + 1]
    return [*ALL_WEEKDAYS[start_index:], *ALL_WEEKDAYS[: end_index + 1]]


def _is_negated(text: str, term: str) -> bool:
    index = text.find(term)
    if index < 0:
        return False
    context = text[max(0, index - 30):index]
    if any(marker in context for marker in ["但是", "可是", "不過"]):
        return False
    return any(marker in context for marker in NEGATION_TERMS)


def _has_negation(text: str) -> bool:
    return any(term in text for term in NEGATION_TERMS)


def _mentions_red_flag(text: str) -> bool:
    return any(term in text for terms in RED_FLAG_BUCKETS.values() for term in terms)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
