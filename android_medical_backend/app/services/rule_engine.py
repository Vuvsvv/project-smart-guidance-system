from __future__ import annotations

import re
import logging
from typing import Any, Optional

from app.schemas import Message, SemanticExtraction, TriageCase, UrgencyResult
from app.services.clarification_engine import clarification_prompt
from app.services.confidence_scoring import ACCEPT_THRESHOLD, MAX_QUESTION_ATTEMPTS, accepted
from app.services.semantic_normalizer import NormalizationResult, normalize_message

logger = logging.getLogger(__name__)


RED_FLAG_PATTERNS = {
    "突發胸痛": ["突發胸痛", "胸痛", "胸悶冒冷汗"],
    "嚴重呼吸困難": ["呼吸困難", "喘不過氣", "無法呼吸"],
    "中風徵象": ["嘴歪", "半邊無力", "說話不清", "中風"],
    "大量出血": ["大量出血", "血流不止"],
    "嚴重外傷": ["嚴重外傷", "車禍", "高處墜落"],
    "意識異常": ["昏迷", "意識不清", "叫不醒"],
    "劇烈頭痛合併神經症狀": ["劇烈頭痛", "視力模糊", "抽搐"],
}

RED_FLAG_QUESTION_KEY = "red_flags"
QUESTION_TEXTS = {
    "symptom": "請描述目前最主要的不舒服症狀。",
    RED_FLAG_QUESTION_KEY: "請問是否有突發胸痛、嚴重呼吸困難、意識不清、大量出血、半邊無力或劇烈頭痛等急迫症狀？",
    "body_part": "請問症狀主要發生在哪個部位？",
    "duration": "請問這個症狀大約持續多久了？",
    "severity": "請問症狀程度是輕微、中等、明顯，還是很痛或影響生活？",
    "preferred_days": "請問你最近哪幾天有空就醫？",
    "preferred_sessions": "請問你偏好的看診時段是上午、下午還是夜間？",
}

RED_FLAG_SCREEN_TERMS = [
    "胸痛",
    "呼吸困難",
    "喘不過氣",
    "意識不清",
    "大量出血",
    "半邊無力",
    "劇烈頭痛",
    "中風",
    "昏迷",
]

NEGATIVE_TERMS = ["沒有", "無", "否", "否認", "都沒有", "都沒", "沒這些", "不會", "沒有以上", "無上述"]
PREFERRED_DAYS_KEY = "preferred_days"
PREFERRED_SESSIONS_KEY = "preferred_sessions"
ALL_WEEKDAYS = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
WEEKDAY_DAYS = ["週一", "週二", "週三", "週四", "週五"]
WEEKEND_DAYS = ["週六", "週日"]
ALL_SESSIONS = ["上午", "下午", "夜間"]
ANY_TIME_TERMS = ["都有空", "都可以", "皆可", "隨時", "任何", "都方便", "都行"]


def apply_user_message(case: TriageCase, message: str) -> TriageCase:
    text = message.strip()
    if not text:
        return case

    before_patient = case.patient_input.model_dump()
    before_availability = case.availability.model_dump()
    case.history_records.append(Message(role="user", content=text))
    patient = case.patient_input
    semantic_result = normalize_message(text, case.conversation_state.last_question_key)
    _apply_semantic_result(case, semantic_result)

    if not patient.symptom:
        patient.symptom = text

    body_part = _extract_body_part(text)
    if body_part and not patient.body_part:
        patient.body_part = body_part

    duration = _extract_duration(text)
    if duration:
        patient.duration = duration

    severity = _extract_severity(text)
    if severity:
        patient.severity = severity

    onset = _extract_onset(text)
    if onset:
        patient.onset = onset

    for symptom in _extract_accompanying_symptoms(text):
        if symptom not in patient.accompanying_symptoms:
            patient.accompanying_symptoms.append(symptom)

    if semantic_result.urgency and semantic_result.urgency.semantic_status == "unavailable":
        positive_red_flags = []
    elif semantic_result.urgency and semantic_result.urgency.matched_red_flags:
        positive_red_flags = semantic_result.urgency.matched_red_flags
    else:
        positive_red_flags = detect_red_flags(text)
    red_flag_answered = _is_red_flag_screen_answer(case, text, positive_red_flags)
    if red_flag_answered:
        patient.red_flags_checked = True
        _consume_field(case, RED_FLAG_QUESTION_KEY, "available" if positive_red_flags else "unavailable", 0.9)
        if not positive_red_flags and _is_negative_red_flag_answer(case, text):
            patient.red_flags = []

    for red_flag in positive_red_flags:
        if red_flag not in patient.red_flags:
            patient.red_flags.append(red_flag)

    availability = case.availability

    _refresh_collected_fields(case)
    logger.info(
        "apply_user_message case_id=%s history_len=%s before_patient=%s after_patient=%s before_availability=%s after_availability=%s red_flags=%s red_flags_checked=%s last_question_key=%s consumed_fields=%s question_attempts=%s field_statuses=%s availability=%s",
        case.case_id,
        len(case.history_records),
        before_patient,
        patient.model_dump(),
        before_availability,
        availability.model_dump(),
        patient.red_flags,
        patient.red_flags_checked,
        case.conversation_state.last_question_key,
        case.conversation_state.consumed_fields,
        case.conversation_state.question_attempts,
        case.conversation_state.field_statuses,
        availability.model_dump(),
    )
    return case


def evaluate_urgency(case: TriageCase) -> UrgencyResult:
    patient = case.patient_input
    _refresh_collected_fields(case)
    combined = " ".join(
        [
            patient.symptom or "",
            patient.body_part or "",
            patient.duration or "",
            patient.severity or "",
            patient.onset or "",
            " ".join(patient.accompanying_symptoms),
            " ".join(patient.red_flags),
        ]
    )

    if patient.urgency_normalized.semantic_status == "unavailable":
        detected_from_combined = []
    elif patient.urgency_normalized.matched_red_flags:
        detected_from_combined = patient.urgency_normalized.matched_red_flags
    else:
        detected_from_combined = detect_red_flags(combined)
    if patient.red_flags_checked and not patient.red_flags:
        red_flags = []
    else:
        red_flags = list(dict.fromkeys([*patient.red_flags, *detected_from_combined]))
    patient.red_flags = red_flags
    if red_flags:
        logger.info(
            "evaluate_urgency case_id=%s high_urgency red_flags=%s red_flags_checked=%s history_len=%s",
            case.case_id,
            red_flags,
            patient.red_flags_checked,
            len(case.history_records),
        )
        return UrgencyResult(
            urgency_score=90,
            urgency_level="high",
            warning_required=True,
            warning_message="症狀較急迫，建議盡快就醫，必要時請假處理。",
            need_more_info=False,
            next_question=None,
            reasons=[
                f"偵測到急迫症狀：{', '.join(red_flags)}",
                "急迫症狀不需等待完整問診即可進入確認與就醫建議。",
            ],
            is_final=True,
        )

    score = 10
    reasons = ["基礎急迫度分數為 10。"]

    severity_score = _score_severity(patient.severity, combined)
    if patient.severity_normalized.sleep_impact:
        severity_score = max(severity_score, 20)
    elif patient.severity_normalized.functional_impact:
        severity_score = max(severity_score, 15)
    score += severity_score
    if severity_score:
        reasons.append(f"症狀程度「{patient.severity or '由描述判斷'}」使急迫度增加 {severity_score} 分。")

    duration_score = _score_duration(patient.duration, combined)
    score += duration_score
    if duration_score:
        reasons.append(f"症狀已持續 {patient.duration or '一段時間'}，急迫度增加 {duration_score} 分。")

    function_score = _score_function_limit(combined)
    score += function_score
    if function_score:
        reasons.append(f"描述包含活動或生活功能受影響，急迫度增加 {function_score} 分。")

    onset_score = _score_onset(patient.onset, combined)
    score += onset_score
    if onset_score:
        reasons.append(f"發作型態「{patient.onset or '由描述判斷'}」使急迫度增加 {onset_score} 分。")

    inflammation_score = _score_inflammation(combined)
    score += inflammation_score
    if inflammation_score:
        reasons.append(f"描述包含發炎或全身不適線索，急迫度增加 {inflammation_score} 分。")

    treatment_score = _score_treatment(combined)
    score += treatment_score
    if treatment_score:
        reasons.append(f"描述包含已處理但未改善，急迫度增加 {treatment_score} 分。")

    risk_score = _score_risk(combined)
    score += risk_score
    if risk_score:
        reasons.append(f"描述包含高風險背景，急迫度增加 {risk_score} 分。")

    score = max(0, min(score, 100))

    next_question = next_question_for(case)
    need_more_info = next_question is not None
    level = urgency_level(score)
    warning_required = level == "high"
    if need_more_info:
        reasons.append(f"資訊尚未完整，下一題：{next_question}")
    else:
        reasons.append("問診必要資訊已完整，可進入使用者確認階段。")

    logger.info(
        "evaluate_urgency case_id=%s history_len=%s need_more_info=%s next_question=%s red_flags=%s red_flags_checked=%s availability=%s collected_fields=%s asked_fields=%s consumed_fields=%s last_question_key=%s question_attempts=%s field_statuses=%s",
        case.case_id,
        len(case.history_records),
        need_more_info,
        next_question,
        patient.red_flags,
        patient.red_flags_checked,
        case.availability.model_dump(),
        patient.collected_fields,
        case.conversation_state.asked_fields,
        case.conversation_state.consumed_fields,
        case.conversation_state.last_question_key,
        case.conversation_state.question_attempts,
        case.conversation_state.field_statuses,
    )

    return UrgencyResult(
        urgency_score=score,
        urgency_level=level,
        warning_required=warning_required,
        warning_message="症狀較急迫，建議盡快就醫，必要時請假處理。" if warning_required else None,
        need_more_info=need_more_info,
        next_question=next_question,
        reasons=reasons,
        is_final=not need_more_info,
    )


def next_question_for(case: TriageCase) -> Optional[str]:
    question_key = _next_question_key(case)
    if question_key is None:
        case.conversation_state.last_question_key = None
        return None

    question_text = _question_text_for(case, question_key)
    _mark_question_asked(case, question_key)
    return question_text


def _next_question_key(case: TriageCase) -> Optional[str]:
    _sync_consumed_fields(case)
    for field in [
        "symptom",
        RED_FLAG_QUESTION_KEY,
        "body_part",
        "duration",
        "severity",
        PREFERRED_DAYS_KEY,
        PREFERRED_SESSIONS_KEY,
    ]:
        if _field_satisfied(case, field):
            continue
        if _question_attempts(case, field) >= MAX_QUESTION_ATTEMPTS:
            _fallback_field(case, field)
            continue
        return field
    return None


def _field_satisfied(case: TriageCase, field: str) -> bool:
    patient = case.patient_input
    availability = case.availability
    state = case.conversation_state
    if field in state.consumed_fields:
        return True

    if field == "symptom":
        return bool(patient.symptom)
    if field == RED_FLAG_QUESTION_KEY:
        if patient.red_flags and not patient.red_flags_checked:
            patient.red_flags_checked = True
        return patient.red_flags_checked
    if field == "body_part":
        return bool(patient.body_part)
    if field == "duration":
        return bool(patient.duration)
    if field == "severity":
        return bool(patient.severity)
    if field == PREFERRED_DAYS_KEY:
        return bool(availability.preferred_days) or state.field_statuses.get(field) == "unavailable"
    if field == PREFERRED_SESSIONS_KEY:
        return bool(availability.preferred_sessions) or state.field_statuses.get(field) == "unavailable"
    return True


def _fallback_field(case: TriageCase, field: str) -> None:
    state = case.conversation_state
    state.field_statuses[field] = state.field_statuses.get(field, "unknown")
    state.field_confidence[field] = state.field_confidence.get(field, 0.0)
    state.clarification_reasons[field] = "max question attempts reached; fallback accepted"
    _consume_field(case, field, state.field_statuses[field], state.field_confidence[field])
    if field == RED_FLAG_QUESTION_KEY:
        case.patient_input.red_flags_checked = True
        case.patient_input.red_flags = []
    elif field == "symptom" and not case.patient_input.symptom:
        case.patient_input.symptom = "unknown"
    elif field == "body_part" and not case.patient_input.body_part:
        case.patient_input.body_part = "unknown"
    elif field == "duration" and not case.patient_input.duration:
        case.patient_input.duration = "unknown"
    elif field == "severity" and not case.patient_input.severity:
        case.patient_input.severity = "unknown"


def _question_text_for(case: TriageCase, field: str) -> str:
    confidence = case.conversation_state.field_confidence.get(field, 1.0)
    status = case.conversation_state.field_statuses.get(field)
    if _question_attempts(case, field) > 0 and (confidence < ACCEPT_THRESHOLD or status in {"unknown", "ambiguous", "unavailable"}):
        return clarification_prompt(field, status)
    return QUESTION_TEXTS[field]


def _question_attempts(case: TriageCase, field: str) -> int:
    return case.conversation_state.question_attempts.get(field, 0)


def urgency_level(score: int) -> str:
    if score >= 60:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _apply_semantic_result(case: TriageCase, result: NormalizationResult) -> None:
    patient = case.patient_input
    if result.severity is not None:
        patient.severity_normalized = result.severity
        if result.severity.severity_level and accepted(result.severity.confidence, result.severity.semantic_status):
            patient.severity = result.severity.severity_level

    if result.urgency is not None:
        patient.urgency_normalized = result.urgency
        if result.urgency.semantic_status == "unavailable" and accepted(result.urgency.confidence, result.urgency.semantic_status):
            patient.red_flags_checked = True
            patient.red_flags = []
            _consume_field(case, RED_FLAG_QUESTION_KEY, "unavailable", result.urgency.confidence)
        elif result.urgency.matched_red_flags and accepted(result.urgency.confidence, result.urgency.semantic_status):
            patient.red_flags_checked = True
            _consume_field(case, RED_FLAG_QUESTION_KEY, "available", result.urgency.confidence)
            for red_flag in result.urgency.matched_red_flags:
                if red_flag not in patient.red_flags:
                    patient.red_flags.append(red_flag)

    for extraction in result.extractions:
        _record_semantic_extraction(case, extraction)
        _apply_semantic_extraction(case, extraction)

    if result.extractions:
        case.semantic_extractions.extend(result.extractions)
        case.semantic_extractions = case.semantic_extractions[-50:]


def _record_semantic_extraction(case: TriageCase, extraction: SemanticExtraction) -> None:
    state = case.conversation_state
    state.field_statuses[extraction.field] = extraction.semantic_status
    state.field_confidence[extraction.field] = extraction.confidence
    if extraction.follow_up_reason:
        state.clarification_reasons[extraction.field] = extraction.follow_up_reason


def _apply_semantic_extraction(case: TriageCase, extraction: SemanticExtraction) -> None:
    availability = case.availability
    if extraction.field in {"preferred_days", "preferred_sessions", "can_take_leave"}:
        availability.semantic_status[extraction.field] = extraction.semantic_status
        availability.confidence[extraction.field] = extraction.confidence

    if not accepted(extraction.confidence, extraction.semantic_status):
        return

    if extraction.field == "preferred_days":
        _merge_list(availability.preferred_days, _as_string_list(extraction.normalized_value))
        _consume_field(case, extraction.field, extraction.semantic_status, extraction.confidence)
    elif extraction.field == "preferred_sessions":
        _merge_list(availability.preferred_sessions, _as_string_list(extraction.normalized_value))
        _consume_field(case, extraction.field, extraction.semantic_status, extraction.confidence)
    elif extraction.field == "can_take_leave" and isinstance(extraction.normalized_value, bool):
        availability.can_take_leave = extraction.normalized_value
        _consume_field(case, extraction.field, extraction.semantic_status, extraction.confidence)
    elif extraction.field == "severity" and isinstance(extraction.normalized_value, dict):
        level = extraction.normalized_value.get("severity_level")
        if level:
            case.patient_input.severity = str(level)
            _consume_field(case, extraction.field, extraction.semantic_status, extraction.confidence)
    elif extraction.field == "red_flags":
        if extraction.semantic_status == "unavailable":
            case.patient_input.red_flags_checked = True
            case.patient_input.red_flags = []
            _consume_field(case, RED_FLAG_QUESTION_KEY, "unavailable", extraction.confidence)
        else:
            flags = _as_string_list(extraction.normalized_value)
            if flags:
                case.patient_input.red_flags_checked = True
                _merge_list(case.patient_input.red_flags, flags)
                _consume_field(case, RED_FLAG_QUESTION_KEY, extraction.semantic_status, extraction.confidence)


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _merge_list(target: list[str], values: list[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _mark_question_asked(case: TriageCase, question_key: str) -> None:
    state = case.conversation_state
    state.last_question_key = question_key
    state.question_attempts[question_key] = state.question_attempts.get(question_key, 0) + 1
    if question_key not in state.asked_fields:
        state.asked_fields.append(question_key)


def _consume_field(
    case: TriageCase,
    field: str,
    status: str | None = None,
    confidence: float | None = None,
) -> None:
    state = case.conversation_state
    if field not in state.consumed_fields:
        state.consumed_fields.append(field)
    if status:
        state.field_statuses[field] = status
    if confidence is not None:
        state.field_confidence[field] = confidence


def _sync_consumed_fields(case: TriageCase) -> None:
    patient = case.patient_input
    availability = case.availability
    if patient.symptom:
        _consume_field(case, "symptom", case.conversation_state.field_statuses.get("symptom"))
    if patient.body_part:
        _consume_field(case, "body_part", case.conversation_state.field_statuses.get("body_part"))
    if patient.duration:
        _consume_field(case, "duration", case.conversation_state.field_statuses.get("duration"))
    if patient.severity:
        _consume_field(case, "severity", case.conversation_state.field_statuses.get("severity"))
    if patient.red_flags_checked:
        _consume_field(
            case,
            RED_FLAG_QUESTION_KEY,
            "available" if patient.red_flags else "unavailable",
            case.conversation_state.field_confidence.get(RED_FLAG_QUESTION_KEY),
        )
    if availability.preferred_days or case.conversation_state.field_statuses.get(PREFERRED_DAYS_KEY) == "unavailable":
        _consume_field(
            case,
            PREFERRED_DAYS_KEY,
            availability.semantic_status.get(PREFERRED_DAYS_KEY) or case.conversation_state.field_statuses.get(PREFERRED_DAYS_KEY),
            availability.confidence.get(PREFERRED_DAYS_KEY) or case.conversation_state.field_confidence.get(PREFERRED_DAYS_KEY),
        )
    if availability.preferred_sessions or case.conversation_state.field_statuses.get(PREFERRED_SESSIONS_KEY) == "unavailable":
        _consume_field(
            case,
            PREFERRED_SESSIONS_KEY,
            availability.semantic_status.get(PREFERRED_SESSIONS_KEY) or case.conversation_state.field_statuses.get(PREFERRED_SESSIONS_KEY),
            availability.confidence.get(PREFERRED_SESSIONS_KEY) or case.conversation_state.field_confidence.get(PREFERRED_SESSIONS_KEY),
        )


def _is_red_flag_screen_answer(
    case: TriageCase,
    text: str,
    positive_red_flags: list[str],
) -> bool:
    if positive_red_flags:
        return True
    if case.conversation_state.last_question_key == RED_FLAG_QUESTION_KEY and _has_negation(text):
        return True
    return _mentions_red_flag_screen(text) and _has_negation(text)


def _is_negative_red_flag_answer(case: TriageCase, text: str) -> bool:
    if not _has_negation(text):
        return False
    if case.conversation_state.last_question_key == RED_FLAG_QUESTION_KEY:
        return True
    return _mentions_red_flag_screen(text)


def _mentions_red_flag_screen(text: str) -> bool:
    return any(term in text for term in RED_FLAG_SCREEN_TERMS)


def _has_negation(text: str) -> bool:
    return any(term in text for term in NEGATIVE_TERMS)


def detect_red_flags(text: str) -> list[str]:
    red_flags = []
    for label, keywords in RED_FLAG_PATTERNS.items():
        if any(keyword in text and not _is_negated_keyword(text, keyword) for keyword in keywords):
            red_flags.append(label)
    return red_flags


def _extract_body_part(text: str) -> Optional[str]:
    parts = ["膝", "膝蓋", "胸", "頭", "腹", "肚子", "眼", "耳", "喉嚨", "皮膚", "腰", "背", "手", "腳"]
    for part in parts:
        if part in text:
            return part
    return None


def _extract_duration(text: str) -> Optional[str]:
    match = re.search(r"(\d+\s*(?:天|週|周|個月|月|年))", text)
    if match:
        return match.group(1).replace(" ", "")
    if "昨天" in text:
        return "1天"
    if "今天" in text:
        return "1天內"
    return None


def _extract_severity(text: str) -> Optional[str]:
    if any(word in text for word in ["很痛", "劇痛", "無法", "嚴重"]):
        return "很痛 / 影響明顯"
    if any(word in text for word in ["明顯", "很不舒服", "走路困難", "爬樓梯很吃力"]):
        return "明顯"
    if any(word in text for word in ["中等", "中度", "還可以忍"]):
        return "中度"
    if any(word in text for word in ["輕微", "一點"]):
        return "輕微"
    return None


def _extract_onset(text: str) -> Optional[str]:
    if any(word in text for word in ["突然", "突發", "一下子"]):
        return "突發"
    if any(word in text for word in ["慢慢", "漸進", "越來越"]):
        return "漸進"
    return None


def _extract_accompanying_symptoms(text: str) -> list[str]:
    symptoms = []
    candidates = ["爬樓梯吃力", "走路困難", "發燒", "紅腫熱痛", "頭暈", "噁心", "麻", "無力"]
    for candidate in candidates:
        if candidate in text:
            symptoms.append(candidate)
    return symptoms


def _extract_preferred_days(text: str, last_question_key: Optional[str] = None) -> list[str]:
    normalized = _normalize_weekday_text(text)
    days: list[str] = []

    if _is_any_days_answer(normalized, last_question_key):
        days.extend(ALL_WEEKDAYS)

    if any(term in normalized for term in ["週一到週五", "週一至週五", "週一-週五", "平日", "工作日", "週間"]):
        days.extend(WEEKDAY_DAYS)

    if any(term in normalized for term in ["週末", "假日", "六日", "週六日", "週六週日"]):
        days.extend(WEEKEND_DAYS)

    range_match = re.search(r"週([一二三四五六日])\s*(?:到|至|-|～|~)\s*週([一二三四五六日])", normalized)
    if range_match:
        days.extend(_weekday_range(f"週{range_match.group(1)}", f"週{range_match.group(2)}"))

    for day in ALL_WEEKDAYS:
        if day in normalized:
            days.append(day)

    return _unique(days)


def _extract_preferred_sessions(text: str, last_question_key: Optional[str] = None) -> list[str]:
    sessions: list[str] = []
    if last_question_key == PREFERRED_SESSIONS_KEY and any(term in text for term in ANY_TIME_TERMS):
        sessions.extend(ALL_SESSIONS)

    if any(term in text for term in ["上午", "早上", "早晨", "一早", "中午前"]):
        sessions.append("上午")
    if any(term in text for term in ["下午", "午後", "中午後"]):
        sessions.append("下午")
    if any(term in text for term in ["夜間", "晚上", "晚間", "夜診", "下班後"]):
        sessions.append("夜間")
    if any(term in text for term in ["全天", "整天", "任何時段"]):
        sessions.extend(ALL_SESSIONS)

    return _unique(sessions)


def _extract_can_take_leave(text: str) -> Optional[bool]:
    if "請假" not in text:
        return None
    if any(term in text for term in ["不能", "不行", "不方便", "沒辦法", "無法"]):
        return False
    if any(term in text for term in ["可以", "能", "可", "願意"]):
        return True
    return None


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


def _is_any_days_answer(text: str, last_question_key: Optional[str]) -> bool:
    if any(term in text for term in ["每天", "整週", "全週", "這幾天都有空", "最近都有空"]):
        return True
    return last_question_key == PREFERRED_DAYS_KEY and any(term in text for term in ANY_TIME_TERMS)


def _weekday_range(start: str, end: str) -> list[str]:
    if start not in ALL_WEEKDAYS or end not in ALL_WEEKDAYS:
        return []
    start_index = ALL_WEEKDAYS.index(start)
    end_index = ALL_WEEKDAYS.index(end)
    if start_index <= end_index:
        return ALL_WEEKDAYS[start_index : end_index + 1]
    return [*ALL_WEEKDAYS[start_index:], *ALL_WEEKDAYS[: end_index + 1]]


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _refresh_collected_fields(case: TriageCase) -> None:
    patient = case.patient_input
    fields = []
    if patient.symptom:
        fields.append("symptom")
    if patient.body_part:
        fields.append("body_part")
    if patient.duration:
        fields.append("duration")
    if patient.severity:
        fields.append("severity")
    if patient.onset:
        fields.append("onset")
    if patient.accompanying_symptoms:
        fields.append("accompanying_symptoms")
    if patient.red_flags:
        fields.append("red_flags")
    if patient.red_flags_checked:
        fields.append("red_flags_checked")
    if case.availability.preferred_days:
        fields.append("preferred_days")
    if case.availability.preferred_sessions:
        fields.append("preferred_sessions")
    patient.collected_fields = fields


def _conversation_text(case: TriageCase) -> str:
    return " ".join(message.content for message in case.history_records)


def _has_urgency_screen_answer(text: str) -> bool:
    if detect_red_flags(text):
        return True
    return _has_negation(text) and _mentions_red_flag_screen(text)


def _is_negated_keyword(text: str, keyword: str) -> bool:
    index = text.find(keyword)
    if index < 0:
        return False
    context = text[max(0, index - 30):index]
    if any(marker in context for marker in ["但", "但是", "可是", "不過"]):
        return False
    return any(marker in context for marker in NEGATIVE_TERMS)


def _score_severity(severity: Optional[str], text: str) -> int:
    value = severity or text
    if value == "severe":
        return 18
    if value == "moderate":
        return 8
    if value == "mild":
        return 3
    if any(word in value for word in ["很痛", "劇痛", "影響明顯", "嚴重"]):
        return 15
    if "明顯" in value:
        return 10
    if any(word in value for word in ["中等", "中度"]):
        return 5
    return 0


def _score_duration(duration: Optional[str], text: str) -> int:
    value = duration or text
    if any(word in value for word in ["6週", "六週", "2個月", "兩個月"]):
        return 8
    if any(word in value for word in ["2週", "兩週", "3週", "一個月", "1個月"]):
        return 5
    if any(word in value for word in ["週", "周", "4天", "5天", "6天", "7天"]):
        return 3
    return 0


def _score_function_limit(text: str) -> int:
    if any(word in text for word in ["幾乎不能活動", "不能活動"]):
        return 20
    if any(word in text for word in ["無法正常活動", "無法走路"]):
        return 15
    if any(word in text for word in ["走路困難", "工作", "爬樓梯很吃力"]):
        return 10
    if "影響" in text:
        return 5
    return 0


def _score_onset(onset: Optional[str], text: str) -> int:
    value = onset or text
    if any(word in value for word in ["快速惡化", "突然變嚴重"]):
        return 10
    if any(word in value for word in ["慢慢變差", "越來越"]):
        return 5
    return 0


def _score_inflammation(text: str) -> int:
    score = 0
    if any(word in text for word in ["發燒", "紅腫熱痛"]):
        score += 5
    if any(word in text for word in ["全身不適", "畏寒"]):
        score += 10
    return score


def _score_treatment(text: str) -> int:
    if any(word in text for word in ["休息沒改善", "止痛沒改善", "吃藥沒改善"]):
        return 5
    return 0


def _score_risk(text: str) -> int:
    score = 0
    if any(word in text for word in ["高齡", "老人", "慢性病", "糖尿病"]):
        score += 5
    if any(word in text for word in ["免疫低下", "化療"]):
        score += 10
    return score
