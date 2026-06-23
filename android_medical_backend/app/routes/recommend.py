from fastapi import APIRouter, HTTPException

from app.schemas import ConversationStage, RecommendRequest, RecommendationResult
from app.services.appointment_service import detect_department_result, recommend_appointments
from app.services.case_store import create_case, get_case, save_case, save_recommendation_result
from app.services.rule_engine import apply_user_message, evaluate_urgency

router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.post("", response_model=RecommendationResult)
async def recommend(req: RecommendRequest) -> RecommendationResult:
    case = req.triage_case or (get_case(req.case_id) if req.case_id else None)
    if case is None and req.userQuery:
        case = create_case(req.case_id)
        apply_user_message(case, req.userQuery)
        case.triage = evaluate_urgency(case)
        case.conversation_state.is_complete = not case.triage.need_more_info

    if case is None:
        raise HTTPException(status_code=400, detail="請提供 triage_case、case_id 或 userQuery。")

    if case.conversation_state.is_complete is not True or case.triage.need_more_info is True:
        raise HTTPException(status_code=400, detail="triage_case 尚未完成，請先完成 /chat 多輪問答。")

    if req.confirmed:
        case.confirmed = True
        case.conversation_state.confirmed = True
        case.conversation_state.awaiting_confirmation = False

    if not (case.confirmed or case.conversation_state.confirmed):
        raise HTTPException(status_code=400, detail="triage_case 尚未確認，請先以 /chat 傳入 confirmed=true。")

    case.confirmed = True
    case.conversation_state.stage = ConversationStage.RECOMMENDING
    case.conversation_state.confirmed = True
    case.conversation_state.awaiting_confirmation = False

    if case.department_result is None:
        case.department_result = await detect_department_result(case)

    result = await recommend_appointments(case)
    case.recommendation_generated = True
    save_case(case)
    save_recommendation_result(result)

    if not result.recommendations.specialty_first or not result.recommendations.time_first:
        raise HTTPException(status_code=503, detail="目前無符合的掛號方案，Azure SQL 與 mock_schedule.json 都沒有可用資料。")
    return result
