package com.example.medicalaiguidance.state

import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.example.medicalaiguidance.network.ChatRequest
import com.example.medicalaiguidance.network.ConversationStateDto
import com.example.medicalaiguidance.network.MedicalApiClient
import com.example.medicalaiguidance.network.RecommendRequest
import com.example.medicalaiguidance.network.RecommendationItemDto
import com.example.medicalaiguidance.network.RecommendationResultDto
import com.example.medicalaiguidance.network.ScriptRequest
import com.example.medicalaiguidance.network.ScriptResponseDto
import com.example.medicalaiguidance.network.TriageResultDto

class TriageFlowController(
    private val apiClient: MedicalApiClient = MedicalApiClient()
) {
    var uiState by mutableStateOf(TriageUiState())
        private set

    suspend fun submitMessage(message: String) {
        val trimmed = message.trim()
        if (trimmed.isBlank()) {
            uiState = uiState.copy(errorMessage = "請先輸入症狀或回答內容。")
            return
        }

        runStep("送出問診內容") {
            val result = apiClient.chat(
                ChatRequest(
                    caseId = uiState.caseId,
                    message = trimmed
                )
            )
            applyTriageResult(result)
            uiState = uiState.copy(
                turns = uiState.turns + ChatTurn(role = "user", content = trimmed) + result.toAssistantTurn()
            )
        }
    }

    suspend fun confirmTriage() {
        val caseId = uiState.caseId
        if (caseId.isNullOrBlank()) {
            uiState = uiState.copy(errorMessage = "目前沒有可確認的問診案件。")
            return
        }

        runStep("確認分診結果") {
            val result = apiClient.chat(
                ChatRequest(
                    caseId = caseId,
                    confirmed = true
                )
            )
            applyTriageResult(result)
            uiState = uiState.copy(turns = uiState.turns + result.toAssistantTurn())
            if (result.conversationState.stage == STAGE_RECOMMENDING) {
                loadRecommendations()
            }
        }
    }

    suspend fun loadRecommendations() {
        val caseId = uiState.caseId
        if (caseId.isNullOrBlank()) {
            uiState = uiState.copy(errorMessage = "缺少 case_id，無法取得推薦。")
            return
        }

        runStep("取得推薦方案") {
            val result = apiClient.recommend(RecommendRequest(caseId = caseId))
            uiState = uiState.copy(
                recommendations = result,
                scriptResponse = null,
                selectedRecommendationId = null
            )
            Log.d(TAG, "Loaded recommendations: total=${result.totalCount}")
        }
    }

    suspend fun selectRecommendation(item: RecommendationItemDto) {
        val caseId = uiState.caseId
        if (caseId.isNullOrBlank()) {
            uiState = uiState.copy(errorMessage = "缺少 case_id，無法產生導引腳本。")
            return
        }

        uiState = uiState.copy(selectedRecommendationId = item.recommendationId)
        runStep("產生導引腳本") {
            val result = apiClient.generateScript(
                ScriptRequest(
                    caseId = caseId,
                    recommendationId = item.recommendationId
                )
            )
            uiState = uiState.copy(scriptResponse = result)
            Log.d(TAG, "Generated script: steps=${result.stepCount}")
        }
    }

    fun clearError() {
        uiState = uiState.copy(errorMessage = null)
    }

    fun reset() {
        uiState = TriageUiState()
    }

    private fun applyTriageResult(result: TriageResultDto) {
        uiState = uiState.copy(
            caseId = result.caseId,
            conversationState = result.conversationState,
            triageResult = result,
            recommendations = if (result.conversationState.stage == STAGE_RECOMMENDING) {
                uiState.recommendations
            } else {
                null
            },
            scriptResponse = null,
            errorMessage = null
        )
        Log.d(TAG, "Triage stage=${result.conversationState.stage}, case=${result.caseId}")
    }

    private suspend fun runStep(loadingMessage: String, block: suspend () -> Unit) {
        uiState = uiState.copy(
            isLoading = true,
            loadingMessage = loadingMessage,
            errorMessage = null
        )
        try {
            block()
        } catch (error: Exception) {
            uiState = uiState.copy(errorMessage = error.message ?: "流程發生未知錯誤。")
        } finally {
            uiState = uiState.copy(
                isLoading = false,
                loadingMessage = null
            )
        }
    }

    private fun TriageResultDto.toAssistantTurn(): ChatTurn {
        val content = reply ?: nextQuestion ?: when (conversationState.stage) {
            STAGE_WAITING_CONFIRMATION -> "分診資訊已整理完成，請確認後取得推薦方案。"
            STAGE_RECOMMENDING -> "已確認分診結果，正在取得推薦方案。"
            else -> "已更新問診結果。"
        }
        return ChatTurn(role = "assistant", content = content)
    }

    companion object {
        private const val TAG = "TriageFlowController"
        const val STAGE_COLLECTING = "collecting"
        const val STAGE_WAITING_CONFIRMATION = "waiting_confirmation"
        const val STAGE_RECOMMENDING = "recommending"
    }
}

data class TriageUiState(
    val caseId: String? = null,
    val conversationState: ConversationStateDto? = null,
    val triageResult: TriageResultDto? = null,
    val recommendations: RecommendationResultDto? = null,
    val selectedRecommendationId: String? = null,
    val scriptResponse: ScriptResponseDto? = null,
    val turns: List<ChatTurn> = emptyList(),
    val isLoading: Boolean = false,
    val loadingMessage: String? = null,
    val errorMessage: String? = null
)

data class ChatTurn(
    val role: String,
    val content: String
)
