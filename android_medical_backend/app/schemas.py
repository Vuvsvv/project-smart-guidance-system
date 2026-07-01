from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConversationStage(str, Enum):
    COLLECTING = "collecting"
    WAITING_CONFIRMATION = "waiting_confirmation"
    RECOMMENDING = "recommending"
    SCRIPT_READY = "script_ready"
    DONE = "done"


class Message(BaseModel):
    role: str
    content: str


class SemanticExtraction(BaseModel):
    field: str
    normalized_value: Any = None
    semantic_status: str = "unknown"
    confidence: float = 0.0
    source_text: str = ""
    needs_clarification: bool = False
    follow_up_reason: Optional[str] = None
    extractor: str = "deterministic"


class SeverityNormalization(BaseModel):
    severity_level: Optional[str] = None
    functional_impact: bool = False
    sleep_impact: bool = False
    confidence: float = 0.0
    semantic_status: str = "unknown"
    source_text: str = ""
    needs_clarification: bool = False
    follow_up_reason: Optional[str] = None


class UrgencyNormalization(BaseModel):
    urgency_level: str = "low"
    matched_red_flags: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    warning_required: bool = False
    semantic_status: str = "unknown"
    source_text: str = ""
    needs_clarification: bool = False
    follow_up_reason: Optional[str] = None


class PatientInput(BaseModel):
    symptom: str = ""
    body_part: Optional[str] = None
    duration: Optional[str] = None
    severity: Optional[str] = None
    onset: Optional[str] = None
    accompanying_symptoms: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    collected_fields: List[str] = Field(default_factory=list)
    red_flags_checked: bool = False
    severity_normalized: SeverityNormalization = Field(default_factory=SeverityNormalization)
    urgency_normalized: UrgencyNormalization = Field(default_factory=UrgencyNormalization)


class Availability(BaseModel):
    preferred_days: List[str] = Field(default_factory=list)
    preferred_sessions: List[str] = Field(default_factory=list)
    can_take_leave: bool = False
    semantic_status: Dict[str, str] = Field(default_factory=dict)
    confidence: Dict[str, float] = Field(default_factory=dict)


class Preferences(BaseModel):
    specialty_priority: bool = True
    doctor_preference: str = "不限"
    hospital_preference: str = "台北榮總"


class ConversationState(BaseModel):
    stage: ConversationStage = ConversationStage.COLLECTING
    is_complete: bool = False
    awaiting_confirmation: bool = False
    confirmed: bool = False
    asked_fields: List[str] = Field(default_factory=list)
    consumed_fields: List[str] = Field(default_factory=list)
    last_question_key: Optional[str] = None
    question_attempts: Dict[str, int] = Field(default_factory=dict)
    field_statuses: Dict[str, str] = Field(default_factory=dict)
    field_confidence: Dict[str, float] = Field(default_factory=dict)
    clarification_reasons: Dict[str, str] = Field(default_factory=dict)


class UrgencyResult(BaseModel):
    urgency_score: Optional[int] = None
    urgency_level: Optional[str] = None
    warning_required: bool = False
    warning_message: Optional[str] = None
    need_more_info: bool = True
    next_question: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    is_final: bool = False


class DepartmentResult(BaseModel):
    parentDept: str = ""
    childDept: str = ""
    confidence: float = 0.0
    reason: List[str] = Field(default_factory=list)


class TriageCase(BaseModel):
    case_id: str
    history_records: List[Message] = Field(default_factory=list)
    patient_input: PatientInput = Field(default_factory=PatientInput)
    availability: Availability = Field(default_factory=Availability)
    preferences: Preferences = Field(default_factory=Preferences)
    triage: UrgencyResult = Field(default_factory=UrgencyResult)
    conversation_state: ConversationState = Field(default_factory=ConversationState)
    department_result: Optional[DepartmentResult] = None
    semantic_extractions: List[SemanticExtraction] = Field(default_factory=list)
    confirmed: bool = False
    recommendation_generated: bool = False
    script_generated: bool = False
    selected_recommendation_id: Optional[str] = None


class ChatRequest(BaseModel):
    case_id: Optional[str] = None
    message: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    triage_case: Optional[TriageCase] = None
    confirmed: bool = False


class TriageResult(BaseModel):
    case_id: str
    triage_case: TriageCase
    conversation_state: ConversationState
    triage: UrgencyResult
    department_result: Optional[DepartmentResult] = None
    next_question: Optional[str] = None
    reply: Optional[str] = None
    needMoreInfo: bool = True
    triage_reasons: List[str] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    recommendation_id: str
    parentDept: str
    childDept: str
    doctor: str
    date: str
    session: str
    slot: str = ""
    score: float
    reasons: List[str] = Field(default_factory=list)
    rank: Optional[int] = None
    is_best_match: bool = False


class RecommendationColumns(BaseModel):
    specialty_first: List[RecommendationItem] = Field(default_factory=list, max_length=5)
    time_first: List[RecommendationItem] = Field(default_factory=list, max_length=5)


class FallbackDepartment(BaseModel):
    parentDept: str
    childDept: str
    reason: str


class RecommendRequest(BaseModel):
    triage_case: Optional[TriageCase] = None
    case_id: Optional[str] = None
    userQuery: Optional[str] = None
    preference: Optional[str] = None
    confirmed: bool = False


class RecommendationResult(BaseModel):
    case_id: str
    recommendations: RecommendationColumns
    fallback_departments: List[FallbackDepartment] = Field(default_factory=list)
    total_count: int = 0


class ScriptRequest(BaseModel):
    case_id: Optional[str] = None
    recommendation_id: str


class ScriptStep(BaseModel):
    action: str
    target: str
    resource_id: Optional[str] = None
    text: Optional[str] = None
    class_name: Optional[str] = None
    description: Optional[str] = None
    delay_ms: int = 0
    retry: int = 0


class ScriptResponse(BaseModel):
    isSuccess: bool
    script_id: str = "vgh_booking_001"
    recommendation_id: Optional[str] = None
    recommendation: Optional[RecommendationItem] = None
    steps: List[ScriptStep] = Field(default_factory=list)
    message: Optional[str] = None
    step_count: int = 0


# ─────────────────────────────────────────────
# 語音端點 schema（/voice/chat）
# 不影響現有 schema，只新增
# ─────────────────────────────────────────────

class VoiceChatResponse(BaseModel):
    """語音聊天回應：文字（字幕）+ 語音（播放）+ 對話狀態"""
    case_id: str
    user_text: str = ""                          # ASR 辨識出長輩說的話（給字幕）
    reply_text: str = ""                          # 系統回覆文字（給字幕）
    reply_audio_base64: str = ""                 # 回覆語音 base64（給播放）
    audio_format: str = "wav"                    # 音訊格式 wav / m4a
    needMoreInfo: bool = True                     # 是否還要繼續問
    stage: str = ""                               # 對話階段
    department_result: Optional[DepartmentResult] = None
    tts_failed: bool = False                      # TTS 失敗時 true，Android 改用系統 TTS 念 reply_text
    error: Optional[str] = None


class VoiceTtsRequest(BaseModel):
    text: str
    lang: str = "chinese"
    speed: float = 1.0


class VoiceTtsResponse(BaseModel):
    audio_base64: str = ""
    audio_format: str = "wav"
    tts_failed: bool = False
    error: Optional[str] = None
