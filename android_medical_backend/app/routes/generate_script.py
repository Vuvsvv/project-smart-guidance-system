from fastapi import APIRouter, HTTPException

from app.schemas import ConversationStage, ScriptRequest, ScriptResponse
from app.services.case_store import find_recommendation, get_case, get_recommendation, save_case
from app.services.script_service import SCRIPT_ID, build_navigation_script

router = APIRouter(prefix="/generate_script", tags=["generate_script"])


@router.post("", response_model=ScriptResponse)
def generate_script(req: ScriptRequest) -> ScriptResponse:
    recommendation = (
        get_recommendation(req.case_id, req.recommendation_id)
        if req.case_id
        else find_recommendation(req.recommendation_id)
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="找不到 case_id / recommendation_id，請先呼叫 /recommend 並選擇其中一筆。")

    steps = build_navigation_script(recommendation)
    if req.case_id:
        case = get_case(req.case_id)
        if case:
            case.selected_recommendation_id = recommendation.recommendation_id
            case.script_generated = True
            case.conversation_state.stage = ConversationStage.SCRIPT_READY
            save_case(case)

    return ScriptResponse(
        isSuccess=True,
        script_id=SCRIPT_ID,
        recommendation_id=recommendation.recommendation_id,
        recommendation=recommendation,
        steps=steps,
        message=f"已產生導引劇本：{recommendation.childDept} / {recommendation.doctor} / {recommendation.date}",
        step_count=len(steps),
    )
