from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.schemas import DepartmentResult, SemanticExtraction, TriageCase, UrgencyResult
from app.services.ai_service import complete_prompt

logger = logging.getLogger(__name__)


@dataclass
class RagTriageSuggestion:
    triage: UrgencyResult | None = None
    reply: str | None = None
    semantic_extractions: list[SemanticExtraction] | None = None


async def refine_case_with_ai(case: TriageCase) -> RagTriageSuggestion | None:
    """Use the rag_demo-style prompt to refine collected symptom fields.

    This is an adapter, not a route dependency. It preserves the current backend
    schema and lets the deterministic rule engine remain the fallback source of
    truth when AI is disabled or returns an invalid payload.
    """
    if not _ai_available():
        logger.info("rag_triage_adapter refine skipped: AI key is not configured")
        return None

    prompt = _build_symptom_collection_prompt(case)
    try:
        raw = await complete_prompt(prompt)
        logger.debug("rag_triage_adapter raw response case_id=%s raw=%s", case.case_id, raw)
        data = _parse_json_object(raw)
    except Exception as exc:
        logger.warning(
            "rag_triage_adapter refine failed case_id=%s error=%s",
            case.case_id,
            exc,
        )
        return None

    patient_data = data.get("patient_input")
    if isinstance(patient_data, dict):
        _merge_patient_input(case, patient_data)

    semantic_extractions = _semantic_extractions_from_ai(data.get("semantic_extractions"))
    if semantic_extractions:
        case.semantic_extractions.extend(semantic_extractions)
        case.semantic_extractions = case.semantic_extractions[-50:]

    triage = None
    triage_data = data.get("triage")
    if isinstance(triage_data, dict):
        triage = _urgency_result_from_ai(triage_data)

    reply = data.get("reply")
    return RagTriageSuggestion(
        triage=triage,
        reply=str(reply).strip() if isinstance(reply, str) and reply.strip() else None,
        semantic_extractions=semantic_extractions,
    )


async def detect_department_with_ai(
    case: TriageCase,
    departments: list[dict[str, Any]],
) -> DepartmentResult | None:
    """Pick a department from the DB-backed department list.

    This ports the useful rag_demo idea into backend service form: the AI sees
    the active DB department names and must return one exact child department.
    Invalid or invented departments are rejected so the caller can fall back to
    deterministic rules.
    """
    if not departments or not _ai_available():
        logger.info(
            "rag_triage_adapter department skipped case_id=%s has_departments=%s ai_available=%s",
            case.case_id,
            bool(departments),
            _ai_available(),
        )
        return None

    child_names = [str(item.get("child_dept", "")).strip() for item in departments if item.get("child_dept")]
    if not child_names:
        return None

    prompt = _build_department_prompt(case, child_names)
    try:
        raw = await complete_prompt(prompt)
        logger.debug("rag_triage_adapter department raw response case_id=%s raw=%s", case.case_id, raw)
        data = _parse_json_object(raw)
    except Exception as exc:
        logger.warning(
            "rag_triage_adapter department parse failed case_id=%s error=%s",
            case.case_id,
            exc,
        )
        return None

    child = str(data.get("childDept") or data.get("dept_name") or "").strip()
    if child not in child_names:
        logger.warning(
            "rag_triage_adapter rejected department case_id=%s child=%s reason=not_in_db_list",
            case.case_id,
            child,
        )
        return None

    parent = _parent_for_child(child, departments)
    reasons = [str(item) for item in data.get("reason", []) if str(item).strip()]
    if not reasons:
        reasons = ["AI 依據問診內容從資料庫科別清單中選出此科別"]
    reasons.append("來源：rag_demo adapter，已限制於後端 DB 科別清單")

    return DepartmentResult(
        parentDept=parent,
        childDept=child,
        confidence=float(data.get("confidence", 0.0) or 0.0),
        reason=reasons,
    )


def merge_ai_next_question(case: TriageCase, suggestion: RagTriageSuggestion | None) -> bool:
    if suggestion is None or suggestion.triage is None:
        return False

    ai_question = suggestion.triage.next_question or suggestion.reply
    if not ai_question:
        return False

    attempted_override = bool(case.triage.next_question)
    if case.triage.next_question:
        logger.info(
            "rag_triage_adapter kept deterministic next_question case_id=%s deterministic=%s ai_question=%s ai_attempted_override=%s last_question_key=%s consumed_fields=%s question_attempts=%s field_statuses=%s availability=%s red_flags_checked=%s next_question=%s",
            case.case_id,
            case.triage.next_question,
            ai_question,
            attempted_override,
            case.conversation_state.last_question_key,
            case.conversation_state.consumed_fields,
            case.conversation_state.question_attempts,
            case.conversation_state.field_statuses,
            case.availability.model_dump(),
            case.patient_input.red_flags_checked,
            case.triage.next_question,
        )
    else:
        logger.info(
            "rag_triage_adapter ignored AI next_question case_id=%s deterministic=%s ai_question=%s ai_attempted_override=%s last_question_key=%s consumed_fields=%s question_attempts=%s field_statuses=%s availability=%s red_flags_checked=%s next_question=%s",
            case.case_id,
            case.triage.next_question,
            ai_question,
            attempted_override,
            case.conversation_state.last_question_key,
            case.conversation_state.consumed_fields,
            case.conversation_state.question_attempts,
            case.conversation_state.field_statuses,
            case.availability.model_dump(),
            case.patient_input.red_flags_checked,
            case.triage.next_question,
        )

    case.triage.reasons.append("AI 追問建議已記錄，但 next_question 由後端 deterministic state machine 決定。")
    return attempted_override


def _ai_available() -> bool:
    return bool(get_settings().google_api_key)


def _build_symptom_collection_prompt_legacy(case: TriageCase) -> str:
    history = "\n".join(
        f"{'使用者' if message.role == 'user' else '助理'}：{message.content}"
        for message in case.history_records
    )
    current_input = case.patient_input.model_dump()

    return f"""你是台北榮民總醫院的分診助理，正在透過對話收集病患症狀。

目前對話紀錄：
{history}

目前已收集到的症狀資料：
{json.dumps(current_input, ensure_ascii=False, indent=2)}

你的任務：
1. 根據對話更新症狀資料。
2. 每次都要判斷急迫程度：
   - high：突發胸痛、呼吸困難、昏迷、大量出血、中風症狀、嚴重過敏。
   - medium：持續高燒、持續嘔吐、劇烈頭痛、視力突然喪失、疑似骨折。
   - low：其他慢性或輕微症狀。
3. 判斷資料是否足夠，至少包含 symptom、body_part、duration、severity、onset、accompanying_symptoms。
4. 如果不夠，每次只提出一個最重要的下一題。
5. 如果 high 急迫，立刻設為完成並提醒盡快就醫。

請只輸出 JSON，不要輸出其他文字：
{{
  "patient_input": {{
    "symptom": "主要症狀描述",
    "body_part": "哪個部位或 null",
    "duration": "持續多久或 null",
    "severity": "嚴重程度或 null",
    "onset": "怎麼開始的或 null",
    "accompanying_symptoms": ["伴隨症狀列表"],
    "red_flags": ["危險警訊列表"]
  }},
  "triage": {{
    "urgency_score": 20,
    "urgency_level": "low",
    "warning_required": false,
    "warning_message": null,
    "need_more_info": true,
    "next_question": "下一題或 null",
    "reasons": ["理由1"],
    "is_final": false
  }},
  "conversation_state": {{
    "stage": "collecting",
    "is_complete": false
  }},
  "reply": "對使用者說的話"
}}"""


def _build_department_prompt(case: TriageCase, child_names: list[str]) -> str:
    dept_list = "\n".join(f"- {name}" for name in child_names)
    symptom_text = _case_text(case)
    return f"""你是台灣醫院掛號分診助理。你只能從下列資料庫科別清單中選一個科別，不可以自行創造科別。

科別清單：
{dept_list}

病患資料：
{symptom_text}

請只輸出 JSON，不要輸出其他文字：
{{
  "childDept": "必須完全符合清單中的科別名稱",
  "confidence": 0.0,
  "reason": ["理由1", "理由2"]
}}"""


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = str(raw).strip().replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("AI response is not a JSON object")
    return data


def _semantic_extractions_from_ai(value: Any) -> list[SemanticExtraction]:
    if not isinstance(value, list):
        return []

    extractions: list[SemanticExtraction] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        try:
            extractions.append(
                SemanticExtraction(
                    field=field,
                    normalized_value=item.get("normalized_value"),
                    semantic_status=str(item.get("semantic_status") or "unknown"),
                    confidence=float(item.get("confidence", 0.0) or 0.0),
                    source_text=str(item.get("source_text") or ""),
                    needs_clarification=bool(item.get("needs_clarification", False)),
                    follow_up_reason=item.get("follow_up_reason"),
                    extractor="ai",
                )
            )
        except (TypeError, ValueError):
            logger.warning("rag_triage_adapter skipped invalid semantic extraction item=%s", item)
    return extractions


def _merge_patient_input(case: TriageCase, data: dict[str, Any]) -> None:
    patient = case.patient_input
    _merge_text(patient, "symptom", data.get("symptom"))
    _merge_text(patient, "body_part", data.get("body_part"))
    _merge_text(patient, "duration", data.get("duration"))
    _merge_text(patient, "severity", data.get("severity"))
    _merge_text(patient, "onset", data.get("onset"))
    _merge_list(patient.accompanying_symptoms, data.get("accompanying_symptoms"))
    if patient.red_flags_checked and not patient.red_flags:
        logger.info(
            "rag_triage_adapter ignored AI red_flags after negative screening case_id=%s ai_red_flags=%s",
            case.case_id,
            data.get("red_flags"),
        )
    else:
        _merge_list(patient.red_flags, data.get("red_flags"))


def _merge_text(target: Any, field: str, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if not text or text.lower() == "null":
        return
    setattr(target, field, text)


def _merge_list(target: list[str], value: Any) -> None:
    if not isinstance(value, list):
        return
    for item in value:
        text = str(item).strip()
        if text and text.lower() != "null" and text not in target:
            target.append(text)


def _urgency_result_from_ai(data: dict[str, Any]) -> UrgencyResult:
    reasons = data.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = []
    return UrgencyResult(
        urgency_score=_optional_int(data.get("urgency_score")),
        urgency_level=str(data.get("urgency_level") or "") or None,
        warning_required=bool(data.get("warning_required", False)),
        warning_message=data.get("warning_message"),
        need_more_info=bool(data.get("need_more_info", True)),
        next_question=data.get("next_question"),
        reasons=[str(item) for item in reasons if str(item).strip()],
        is_final=bool(data.get("is_final", False)),
    )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _parent_for_child(child: str, departments: list[dict[str, Any]]) -> str:
    for item in departments:
        if item.get("child_dept") == child:
            return str(item.get("parent_dept") or "")
    return ""


def _build_symptom_collection_prompt(case: TriageCase) -> str:
    history = "\n".join(
        f"{'使用者' if message.role == 'user' else '助理'}: {message.content}"
        for message in case.history_records
    )
    current_input = case.patient_input.model_dump()

    return f"""你是醫療問診的語意抽取器。你只能做 extraction、normalization、confidence estimation。
不要決定 next_question、stage、waiting_confirmation 或流程轉移，這些一律由 backend deterministic state machine 控制。

目前對話紀錄：
{history}

目前已收集到的症狀資料：{json.dumps(current_input, ensure_ascii=False, indent=2)}

你的任務：
1. 將使用者自然語言整理成 semantic_extractions。
2. semantic_status 只能使用 available、unavailable、unknown、partial、ambiguous。
3. confidence 使用 0 到 1。
4. 若信心不足，設定 needs_clarification=true 與 follow_up_reason。
5. 不要主導流程；triage.next_question 請填 null。

請只輸出 JSON，不要輸出其他文字：
{{
  "semantic_extractions": [
    {{
      "field": "preferred_days",
      "normalized_value": ["週一", "週二"],
      "semantic_status": "partial",
      "confidence": 0.82,
      "source_text": "週一週二可以",
      "needs_clarification": false,
      "follow_up_reason": null
    }}
  ],
  "patient_input": {{
    "symptom": "主要症狀描述",
    "body_part": "哪個部位或 null",
    "duration": "持續多久或 null",
    "severity": "mild | moderate | severe 或 null",
    "onset": "怎麼開始的或 null",
    "accompanying_symptoms": ["伴隨症狀列表"],
    "red_flags": ["危險警訊列表"]
  }},
  "triage": {{
    "urgency_score": 20,
    "urgency_level": "low",
    "warning_required": false,
    "warning_message": null,
    "need_more_info": true,
    "next_question": null,
    "reasons": ["理由1"],
    "is_final": false
  }},
  "reply": null
}}"""
