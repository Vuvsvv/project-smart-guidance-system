import logging

from fastapi import APIRouter

from app.schemas import ChatRequest, ConversationStage, TriageCase, TriageResult
from app.services.appointment_service import detect_department_result
from app.services.case_store import create_case, get_case, save_case
from app.services.rag_triage_adapter import merge_ai_next_question, refine_case_with_ai
from app.services.rule_engine import apply_user_message, evaluate_urgency

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=TriageResult)
async def chat(req: ChatRequest) -> TriageResult:
    case = req.triage_case or (get_case(req.case_id) if req.case_id else None) or create_case(req.case_id)
    logger.info(
        "chat request case_id=%s confirmed=%s has_message=%s has_triage_case=%s history_len=%s stage=%s",
        case.case_id,
        req.confirmed,
        bool(req.message),
        req.triage_case is not None,
        len(case.history_records),
        case.conversation_state.stage,
    )

    ai_suggestion = None
    has_user_input = False
    before_patient = case.patient_input.model_dump()
    before_availability = case.availability.model_dump()
    messages = req.messages or []
    if req.message:
        apply_user_message(case, req.message)
        has_user_input = True
    elif messages:
        for message in messages:
            if message.role == "user":
                apply_user_message(case, message.content)
                has_user_input = True
    if has_user_input:
        logger.info(
            "chat patient updated case_id=%s before_patient=%s after_patient=%s before_availability=%s after_availability=%s last_question_key=%s history_len=%s",
            case.case_id,
            before_patient,
            case.patient_input.model_dump(),
            before_availability,
            case.availability.model_dump(),
            case.conversation_state.last_question_key,
            len(case.history_records),
        )

    _sync_confirmation_flags(case)
    if has_user_input:
        ai_suggestion = await refine_case_with_ai(case)

    case.triage = evaluate_urgency(case)
    ai_attempted_override = merge_ai_next_question(case, ai_suggestion)
    case.conversation_state.is_complete = not case.triage.need_more_info
    logger.info(
        "chat triage evaluated case_id=%s need_more_info=%s next_question=%s red_flags=%s red_flags_checked=%s availability=%s last_question_key=%s consumed_fields=%s question_attempts=%s field_statuses=%s field_confidence=%s ai_attempted_override=%s",
        case.case_id,
        case.triage.need_more_info,
        case.triage.next_question,
        case.patient_input.red_flags,
        case.patient_input.red_flags_checked,
        case.availability.model_dump(),
        case.conversation_state.last_question_key,
        case.conversation_state.consumed_fields,
        case.conversation_state.question_attempts,
        case.conversation_state.field_statuses,
        case.conversation_state.field_confidence,
        ai_attempted_override,
    )

    if not case.triage.need_more_info:
        case.department_result = await detect_department_result(case)

    if case.triage.need_more_info:
        case.confirmed = False
        case.conversation_state.stage = ConversationStage.COLLECTING
        case.conversation_state.awaiting_confirmation = False
        case.conversation_state.confirmed = False
    elif req.confirmed:
        case.confirmed = True
        case.conversation_state.stage = ConversationStage.RECOMMENDING
        case.conversation_state.awaiting_confirmation = False
        case.conversation_state.confirmed = True
    elif case.confirmed or case.conversation_state.confirmed:
        case.confirmed = True
        case.conversation_state.stage = ConversationStage.RECOMMENDING
        case.conversation_state.awaiting_confirmation = False
        case.conversation_state.confirmed = True
    else:
        case.confirmed = False
        case.conversation_state.stage = ConversationStage.WAITING_CONFIRMATION
        case.conversation_state.awaiting_confirmation = True
        case.conversation_state.confirmed = False

    save_case(case)
    logger.info(
        "chat response case_id=%s stage=%s is_complete=%s awaiting_confirmation=%s confirmed=%s history_len=%s next_question=%s last_question_key=%s consumed_fields=%s availability=%s question_attempts=%s field_statuses=%s red_flags_checked=%s ai_attempted_override=%s",
        case.case_id,
        case.conversation_state.stage,
        case.conversation_state.is_complete,
        case.conversation_state.awaiting_confirmation,
        case.conversation_state.confirmed,
        len(case.history_records),
        case.triage.next_question,
        case.conversation_state.last_question_key,
        case.conversation_state.consumed_fields,
        case.availability.model_dump(),
        case.conversation_state.question_attempts,
        case.conversation_state.field_statuses,
        case.patient_input.red_flags_checked,
        ai_attempted_override,
    )

    reply = case.triage.next_question
    if reply is None and case.conversation_state.awaiting_confirmation and case.department_result:
        reply = f"目前建議科別為 {case.department_result.childDept}，請確認後取得推薦掛號方案。"
    elif reply is None and case.conversation_state.confirmed:
        reply = "已確認分診結果，可呼叫 /recommend 取得推薦掛號方案。"

    return TriageResult(
        case_id=case.case_id,
        triage_case=case,
        conversation_state=case.conversation_state,
        triage=case.triage,
        department_result=case.department_result,
        next_question=case.triage.next_question,
        reply=reply,
        needMoreInfo=case.triage.need_more_info,
        triage_reasons=case.triage.reasons,
    )


def _sync_confirmation_flags(case: TriageCase) -> None:
    if case.confirmed:
        case.conversation_state.confirmed = True
        case.conversation_state.awaiting_confirmation = False
