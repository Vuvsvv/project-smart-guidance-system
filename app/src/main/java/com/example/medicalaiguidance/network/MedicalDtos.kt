package com.example.medicalaiguidance.network

import org.json.JSONArray
import org.json.JSONObject

data class ChatRequest(
    val caseId: String? = null,
    val message: String? = null,
    val confirmed: Boolean = false
)

data class RecommendRequest(
    val caseId: String,
    val confirmed: Boolean = false
)

data class ScriptRequest(
    val caseId: String,
    val recommendationId: String
)

data class MessageDto(
    val role: String,
    val content: String
)

data class PatientInputDto(
    val symptom: String = "",
    val bodyPart: String? = null,
    val duration: String? = null,
    val severity: String? = null,
    val onset: String? = null,
    val accompanyingSymptoms: List<String> = emptyList(),
    val redFlags: List<String> = emptyList(),
    val collectedFields: List<String> = emptyList(),
    val redFlagsChecked: Boolean = false
)

data class AvailabilityDto(
    val preferredDays: List<String> = emptyList(),
    val preferredSessions: List<String> = emptyList(),
    val canTakeLeave: Boolean = false,
    val semanticStatus: Map<String, String> = emptyMap(),
    val confidence: Map<String, Double> = emptyMap()
)

data class PreferencesDto(
    val specialtyPriority: Boolean = true,
    val doctorPreference: String = "不限",
    val hospitalPreference: String = "台北榮總"
)

data class ConversationStateDto(
    val stage: String = "collecting",
    val isComplete: Boolean = false,
    val awaitingConfirmation: Boolean = false,
    val confirmed: Boolean = false,
    val askedFields: List<String> = emptyList(),
    val consumedFields: List<String> = emptyList(),
    val lastQuestionKey: String? = null,
    val questionAttempts: Map<String, Int> = emptyMap(),
    val fieldStatuses: Map<String, String> = emptyMap(),
    val fieldConfidence: Map<String, Double> = emptyMap(),
    val clarificationReasons: Map<String, String> = emptyMap()
)

data class UrgencyResultDto(
    val urgencyScore: Int? = null,
    val urgencyLevel: String? = null,
    val warningRequired: Boolean = false,
    val warningMessage: String? = null,
    val needMoreInfo: Boolean = true,
    val nextQuestion: String? = null,
    val reasons: List<String> = emptyList(),
    val isFinal: Boolean = false
)

data class DepartmentResultDto(
    val parentDept: String = "",
    val childDept: String = "",
    val confidence: Double = 0.0,
    val reason: List<String> = emptyList()
)

data class TriageCaseDto(
    val caseId: String,
    val historyRecords: List<MessageDto> = emptyList(),
    val patientInput: PatientInputDto = PatientInputDto(),
    val availability: AvailabilityDto = AvailabilityDto(),
    val preferences: PreferencesDto = PreferencesDto(),
    val triage: UrgencyResultDto = UrgencyResultDto(),
    val conversationState: ConversationStateDto = ConversationStateDto(),
    val departmentResult: DepartmentResultDto? = null,
    val confirmed: Boolean = false,
    val recommendationGenerated: Boolean = false,
    val scriptGenerated: Boolean = false
)

data class TriageResultDto(
    val caseId: String,
    val triageCase: TriageCaseDto?,
    val conversationState: ConversationStateDto,
    val triage: UrgencyResultDto,
    val departmentResult: DepartmentResultDto? = null,
    val nextQuestion: String? = null,
    val reply: String? = null,
    val needMoreInfo: Boolean = true,
    val triageReasons: List<String> = emptyList()
)

data class RecommendationItemDto(
    val recommendationId: String,
    val parentDept: String,
    val childDept: String,
    val doctor: String,
    val date: String,
    val session: String,
    val slot: String = "",
    val score: Double,
    val reasons: List<String> = emptyList(),
    val rank: Int? = null,
    val isBestMatch: Boolean = false
)

data class RecommendationColumnsDto(
    val specialtyFirst: List<RecommendationItemDto> = emptyList(),
    val timeFirst: List<RecommendationItemDto> = emptyList()
)

data class FallbackDepartmentDto(
    val parentDept: String,
    val childDept: String,
    val reason: String
)

data class RecommendationResultDto(
    val caseId: String,
    val recommendations: RecommendationColumnsDto,
    val fallbackDepartments: List<FallbackDepartmentDto> = emptyList(),
    val totalCount: Int = 0
)

data class ScriptStepDto(
    val action: String,
    val target: String,
    val resourceId: String? = null,
    val text: String? = null,
    val className: String? = null,
    val description: String? = null,
    val delayMs: Int = 0,
    val retry: Int = 0
)

data class ScriptResponseDto(
    val isSuccess: Boolean,
    val scriptId: String = "vgh_booking_001",
    val recommendationId: String? = null,
    val steps: List<ScriptStepDto> = emptyList(),
    val message: String? = null,
    val stepCount: Int = 0
)

fun ChatRequest.toJson(): String = JSONObject().apply {
    caseId?.let { put("case_id", it) }
    message?.let { put("message", it) }
    if (confirmed) put("confirmed", true)
}.toString()

fun RecommendRequest.toJson(): String = JSONObject().apply {
    put("case_id", caseId)
    if (confirmed) put("confirmed", true)
}.toString()

fun ScriptRequest.toJson(): String = JSONObject().apply {
    put("case_id", caseId)
    put("recommendation_id", recommendationId)
}.toString()

fun parseTriageResult(json: String): TriageResultDto {
    val obj = JSONObject(json)
    return TriageResultDto(
        caseId = obj.optString("case_id"),
        triageCase = obj.optObject("triage_case")?.toTriageCaseDto(),
        conversationState = obj.optObject("conversation_state")?.toConversationStateDto() ?: ConversationStateDto(),
        triage = obj.optObject("triage")?.toUrgencyResultDto() ?: UrgencyResultDto(),
        departmentResult = obj.optObject("department_result")?.toDepartmentResultDto(),
        nextQuestion = obj.optNullableString("next_question"),
        reply = obj.optNullableString("reply"),
        needMoreInfo = obj.optBoolean("needMoreInfo", true),
        triageReasons = obj.optArray("triage_reasons").toStringList()
    )
}

fun parseRecommendationResult(json: String): RecommendationResultDto {
    val obj = JSONObject(json)
    val recommendations = obj.optObject("recommendations")
    return RecommendationResultDto(
        caseId = obj.optString("case_id"),
        recommendations = RecommendationColumnsDto(
            specialtyFirst = recommendations?.optArray("specialty_first").toRecommendationList(),
            timeFirst = recommendations?.optArray("time_first").toRecommendationList()
        ),
        fallbackDepartments = obj.optArray("fallback_departments").toFallbackDepartmentList(),
        totalCount = obj.optInt("total_count", 0)
    )
}

fun parseScriptResponse(json: String): ScriptResponseDto {
    val obj = JSONObject(json)
    return ScriptResponseDto(
        isSuccess = obj.optBoolean("isSuccess", false),
        scriptId = obj.optString("script_id", "vgh_booking_001"),
        recommendationId = obj.optNullableString("recommendation_id"),
        steps = obj.optArray("steps").toScriptStepList(),
        message = obj.optNullableString("message"),
        stepCount = obj.optInt("step_count", 0)
    )
}

private fun JSONObject.toTriageCaseDto(): TriageCaseDto = TriageCaseDto(
    caseId = optString("case_id"),
    historyRecords = optArray("history_records").toMessageList(),
    patientInput = optObject("patient_input")?.toPatientInputDto() ?: PatientInputDto(),
    availability = optObject("availability")?.toAvailabilityDto() ?: AvailabilityDto(),
    preferences = optObject("preferences")?.toPreferencesDto() ?: PreferencesDto(),
    triage = optObject("triage")?.toUrgencyResultDto() ?: UrgencyResultDto(),
    conversationState = optObject("conversation_state")?.toConversationStateDto() ?: ConversationStateDto(),
    departmentResult = optObject("department_result")?.toDepartmentResultDto(),
    confirmed = optBoolean("confirmed", false),
    recommendationGenerated = optBoolean("recommendation_generated", false),
    scriptGenerated = optBoolean("script_generated", false)
)

private fun JSONObject.toPatientInputDto(): PatientInputDto = PatientInputDto(
    symptom = optString("symptom", ""),
    bodyPart = optNullableString("body_part"),
    duration = optNullableString("duration"),
    severity = optNullableString("severity"),
    onset = optNullableString("onset"),
    accompanyingSymptoms = optArray("accompanying_symptoms").toStringList(),
    redFlags = optArray("red_flags").toStringList(),
    collectedFields = optArray("collected_fields").toStringList(),
    redFlagsChecked = optBoolean("red_flags_checked", false)
)

private fun JSONObject.toAvailabilityDto(): AvailabilityDto = AvailabilityDto(
    preferredDays = optArray("preferred_days").toStringList(),
    preferredSessions = optArray("preferred_sessions").toStringList(),
    canTakeLeave = optBoolean("can_take_leave", false),
    semanticStatus = optObject("semantic_status").toStringMap(),
    confidence = optObject("confidence").toDoubleMap()
)

private fun JSONObject.toPreferencesDto(): PreferencesDto = PreferencesDto(
    specialtyPriority = optBoolean("specialty_priority", true),
    doctorPreference = optString("doctor_preference", "不限"),
    hospitalPreference = optString("hospital_preference", "台北榮總")
)

private fun JSONObject.toConversationStateDto(): ConversationStateDto = ConversationStateDto(
    stage = optString("stage", "collecting"),
    isComplete = optBoolean("is_complete", false),
    awaitingConfirmation = optBoolean("awaiting_confirmation", false),
    confirmed = optBoolean("confirmed", false),
    askedFields = optArray("asked_fields").toStringList(),
    consumedFields = optArray("consumed_fields").toStringList(),
    lastQuestionKey = optNullableString("last_question_key"),
    questionAttempts = optObject("question_attempts").toIntMap(),
    fieldStatuses = optObject("field_statuses").toStringMap(),
    fieldConfidence = optObject("field_confidence").toDoubleMap(),
    clarificationReasons = optObject("clarification_reasons").toStringMap()
)

private fun JSONObject.toUrgencyResultDto(): UrgencyResultDto = UrgencyResultDto(
    urgencyScore = optNullableInt("urgency_score"),
    urgencyLevel = optNullableString("urgency_level"),
    warningRequired = optBoolean("warning_required", false),
    warningMessage = optNullableString("warning_message"),
    needMoreInfo = optBoolean("need_more_info", true),
    nextQuestion = optNullableString("next_question"),
    reasons = optArray("reasons").toStringList(),
    isFinal = optBoolean("is_final", false)
)

private fun JSONObject.toDepartmentResultDto(): DepartmentResultDto = DepartmentResultDto(
    parentDept = optString("parentDept", ""),
    childDept = optString("childDept", ""),
    confidence = optDouble("confidence", 0.0),
    reason = optArray("reason").toStringList()
)

private fun JSONArray?.toMessageList(): List<MessageDto> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { index ->
        optJSONObject(index)?.let {
            MessageDto(
                role = it.optString("role"),
                content = it.optString("content")
            )
        }
    }
}

private fun JSONArray?.toRecommendationList(): List<RecommendationItemDto> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { index ->
        optJSONObject(index)?.let {
            RecommendationItemDto(
                recommendationId = it.optString("recommendation_id"),
                parentDept = it.optString("parentDept"),
                childDept = it.optString("childDept"),
                doctor = it.optString("doctor"),
                date = it.optString("date"),
                session = it.optString("session"),
                slot = it.optString("slot", ""),
                score = it.optDouble("score", 0.0),
                reasons = it.optArray("reasons").toStringList(),
                rank = it.optNullableInt("rank"),
                isBestMatch = it.optBoolean("is_best_match", false)
            )
        }
    }
}

private fun JSONArray?.toFallbackDepartmentList(): List<FallbackDepartmentDto> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { index ->
        optJSONObject(index)?.let {
            FallbackDepartmentDto(
                parentDept = it.optString("parentDept"),
                childDept = it.optString("childDept"),
                reason = it.optString("reason")
            )
        }
    }
}

private fun JSONArray?.toScriptStepList(): List<ScriptStepDto> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { index ->
        optJSONObject(index)?.let {
            ScriptStepDto(
                action = it.optString("action"),
                target = it.optString("target"),
                resourceId = it.optNullableString("resource_id"),
                text = it.optNullableString("text"),
                className = it.optNullableString("class_name"),
                description = it.optNullableString("description"),
                delayMs = it.optInt("delay_ms", 0),
                retry = it.optInt("retry", 0)
            )
        }
    }
}

private fun JSONArray?.toStringList(): List<String> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { index -> opt(index)?.toString() }
}

private fun JSONObject?.toStringMap(): Map<String, String> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { key -> optString(key) }
}

private fun JSONObject?.toIntMap(): Map<String, Int> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { key -> optInt(key, 0) }
}

private fun JSONObject?.toDoubleMap(): Map<String, Double> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { key -> optDouble(key, 0.0) }
}

private fun JSONObject.optObject(name: String): JSONObject? =
    if (isNull(name)) null else optJSONObject(name)

private fun JSONObject.optArray(name: String): JSONArray? =
    if (isNull(name)) null else optJSONArray(name)

private fun JSONObject.optNullableString(name: String): String? =
    if (isNull(name)) null else optString(name)

private fun JSONObject.optNullableInt(name: String): Int? =
    if (isNull(name)) null else optInt(name)
