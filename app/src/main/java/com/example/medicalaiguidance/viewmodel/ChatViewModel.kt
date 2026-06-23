package com.example.medicalaiguidance.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.medicalaiguidance.model.ChatMessage
import com.example.medicalaiguidance.model.HistoryStatus
import com.example.medicalaiguidance.model.MessageSender
import com.example.medicalaiguidance.repository.MedicalRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ChatViewModel(
    private val repository: MedicalRepository = MedicalRepository()
) : ViewModel() {
    private val _inputText = MutableStateFlow("")
    val inputText: StateFlow<String> = _inputText.asStateFlow()

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    private val _isAiThinking = MutableStateFlow(false)
    val isAiThinking: StateFlow<Boolean> = _isAiThinking.asStateFlow()

    private val _showDoctorButton = MutableStateFlow(false)
    val showDoctorButton: StateFlow<Boolean> = _showDoctorButton.asStateFlow()

    private val _showDecisionButtons = MutableStateFlow(false)
    val showDecisionButtons: StateFlow<Boolean> = _showDecisionButtons.asStateFlow()

    private val _isListening = MutableStateFlow(false)
    val isListening: StateFlow<Boolean> = _isListening.asStateFlow()

    private var caseId: String? = null
    private var activeHistoryId: String = "hist_${System.currentTimeMillis()}"
    private var openedHistoryId: String? = null

    init {
        _messages.value = repository.getChatMessages().toList()
    }

    fun onInputTextChanged(text: String) {
        _inputText.value = text
    }

    fun startNewConversation() {
        openedHistoryId = null
        caseId = null
        activeHistoryId = "hist_${System.currentTimeMillis()}"
        _inputText.value = ""
        _showDecisionButtons.value = false
        _showDoctorButton.value = false
        repository.clearChatMessages()
        _messages.value = emptyList()
    }

    fun openHistory(historyId: String) {
        if (openedHistoryId == historyId) return
        openedHistoryId = historyId
        activeHistoryId = historyId
        caseId = historyId.takeIf { it.startsWith("case_") }
        _inputText.value = ""
        val history = repository.loadHistoryIntoCurrentChat(historyId)
        val shouldShowDecisionButtons = history?.status == HistoryStatus.COMPLETED
        _showDecisionButtons.value = shouldShowDecisionButtons
        _showDoctorButton.value = shouldShowDecisionButtons
        _messages.value = repository.getChatMessages().toList()
    }

    fun sendMessage(onAnalysisComplete: () -> Unit) {
        val text = _inputText.value.trim()
        if (text.isBlank() || _isAiThinking.value) return

        viewModelScope.launch {
            repository.addMessage(ChatMessage(content = text, sender = MessageSender.USER))
            _messages.value = repository.getChatMessages().toList()
            _inputText.value = ""
            _isAiThinking.value = true
            _showDecisionButtons.value = false

            try {
                val result = repository.chat(caseId = caseId, message = text)
                caseId = result.caseId

                val reply = result.reply
                    ?: result.nextQuestion
                    ?: result.triage.warningMessage
                    ?: "I received your information. Please continue describing your symptoms or preferred visit time."

                repository.addMessage(ChatMessage(content = reply, sender = MessageSender.AI))

                val stage = result.conversationState.stage
                val readyForRecommendation =
                    stage == "waiting_confirmation" ||
                        stage == "recommending" ||
                        (!result.needMoreInfo && result.triage.isFinal)

                _showDecisionButtons.value = readyForRecommendation
                _showDoctorButton.value = readyForRecommendation
                saveHistory(completed = readyForRecommendation, summary = reply)

                if (stage == "recommending") {
                    onAnalysisComplete()
                }
            } catch (error: Exception) {
                val message = error.message ?: "Unable to connect to the backend server. Please try again later."
                repository.addMessage(ChatMessage(content = message, sender = MessageSender.AI))
                saveHistory(completed = false, summary = message)
            } finally {
                _messages.value = repository.getChatMessages().toList()
                _isAiThinking.value = false
            }
        }
    }

    fun setListening(isListening: Boolean) {
        _isListening.value = isListening
    }

    fun submitVoiceInput(text: String, onAnalysisComplete: () -> Unit) {
        val transcript = text.trim()
        if (transcript.isBlank()) return

        _inputText.value = transcript
        sendMessage(onAnalysisComplete)
    }

    fun chooseRecommendation() {
        _showDecisionButtons.value = false
        _showDoctorButton.value = false
    }

    fun continueEditing() {
        _showDecisionButtons.value = false
        _showDoctorButton.value = false
        saveHistory(
            completed = false,
            summary = repository.getChatMessages()
                .lastOrNull { it.sender == MessageSender.AI }
                ?.content
                ?: "繼續問診中"
        )
    }

    private fun saveHistory(completed: Boolean, summary: String) {
        repository.saveCurrentChatToHistory(
            historyId = caseId ?: activeHistoryId,
            summaryText = summary,
            completed = completed
        )
    }
}
