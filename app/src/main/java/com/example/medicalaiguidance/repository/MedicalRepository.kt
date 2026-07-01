package com.example.medicalaiguidance.repository

import android.content.Context
import com.example.medicalaiguidance.model.Appointment
import com.example.medicalaiguidance.model.ChatMessage
import com.example.medicalaiguidance.model.Department
import com.example.medicalaiguidance.model.Doctor
import com.example.medicalaiguidance.model.History
import com.example.medicalaiguidance.model.HistoryStatus
import com.example.medicalaiguidance.model.MessageSender
import com.example.medicalaiguidance.network.ChatRequest
import com.example.medicalaiguidance.network.MedicalApiClient
import com.example.medicalaiguidance.network.RecommendRequest
import com.example.medicalaiguidance.network.RecommendationResultDto
import com.example.medicalaiguidance.network.ScriptRequest
import com.example.medicalaiguidance.network.ScriptResponseDto
import com.example.medicalaiguidance.network.TriageResultDto
import com.example.medicalaiguidance.network.TtsRequest
import com.example.medicalaiguidance.network.VoiceChatResponseDto
import com.example.medicalaiguidance.network.VoiceTtsResponseDto
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import org.json.JSONArray
import org.json.JSONObject

class MedicalRepository(
    private val apiClient: MedicalApiClient = MedicalApiClient()
) {
    companion object {
        private const val PREFS_NAME = "medical_guidance_history"
        private const val HISTORY_KEY = "history_items"

        private var appContext: Context? = null
        private var currentDepartment: Department? = null
        private var currentDoctor: Doctor? = null
        private var currentDayOfWeek: String = "週一"
        private var currentTimeSlot: String = "上午"
        private val chatMessages = mutableListOf<ChatMessage>()
        private val historyItems = mutableListOf<History>()
        private var historyLoaded = false

        fun initialize(context: Context) {
            appContext = context.applicationContext
            loadHistoryIfNeeded()
        }

        private fun loadHistoryIfNeeded() {
            if (historyLoaded) return
            historyLoaded = true
            val stored = appContext
                ?.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                ?.getString(HISTORY_KEY, null)

            if (stored.isNullOrBlank()) {
                historyItems.clear()
                return
            }

            runCatching {
                val array = JSONArray(stored)
                historyItems.clear()
                for (index in 0 until array.length()) {
                    historyItems.add(array.getJSONObject(index).toHistory())
                }
            }
        }

        private fun persistHistory() {
            val context = appContext ?: return
            val array = JSONArray()
            historyItems.forEach { history -> array.put(history.toJson()) }
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(HISTORY_KEY, array.toString())
                .apply()
        }
    }

    private val departments = listOf(
        Department("dept_orthopedics", "骨科", "一般骨科"),
        Department("dept_eye", "眼科", "一般眼科"),
        Department("dept_family", "家醫科", "家庭醫學科")
    )

    private val doctors = listOf(
        Doctor(
            id = "doc_01",
            name = "蘇宇平",
            departmentId = "dept_01",
            title = "主治醫師",
            specialties = listOf(
                "1. 各類成人及兒童創傷性骨折",
                "2. 微創人工膝髖關節置換手術",
                "3. 人工膝髖關節再置換手術",
                "4. 兒童發展性肢體結構異常",
                "5. 電腦導航手術",
                "6. 關節矯正手術"
            ),
            imageUrl = "https://www.vghtpe.gov.tw/manage/upload/teacher/thumbnails/img_1707100066953.jpg",
            availableSlots = listOf(
                "二" to "上午",
                "五" to "上午",
                "五" to "下午"
            )
        ),
        Doctor(
            id = "doc_02",
            name = "邱方遙",
            departmentId = "dept_01",
            title = "科主任",
            specialties = listOf(
                "1. 人工關節置換術、骨折外傷、不癒合、微創、矯正截骨、骨延長、長短腳、骨盆骨折",
                "2. 髖關節脫臼、關節炎、骨質疏鬆、運動傷害",
                "3. 成人複雜性骨折"
            ),
            imageUrl = "https://www.vghtpe.gov.tw/manage/upload/teacher/thumbnails/img_1498461523534.jpg",
            availableSlots = listOf(
                "一" to "下午",
                "三" to "下午",
                "五" to "上午"
            )
        ),
        Doctor(
            id = "doc_03",
            name = "許逵翔",
            departmentId = "dept_01",
            title = "主治醫師",
            specialties = listOf(
                "1. 髖關節保留手術",
                "2. 肌肉骨骼超音波",
                "3. 人工膝髖關節置換",
                "4. 各種骨折創傷手術",
                "5. 再生醫療及精準醫療",
                "6. 先天性髖關節發育不良",
                "7. 兒童發展性肢體結構異常",
                "8. 兒童及青少年運動醫學",
                "9. 兒童及青少年骨折處理"
            ),
            imageUrl = "https://www.vghtpe.gov.tw/manage/upload/teacher/thumbnails/img_1707099872561.jpg",
            availableSlots = listOf(
                "三" to "上午"
            )
        )
    )

    suspend fun chat(caseId: String?, message: String): TriageResultDto =
        apiClient.chat(ChatRequest(caseId = caseId, message = message)).also { result ->
            val departmentResult = result.departmentResult ?: result.triageCase?.departmentResult
            if (departmentResult != null && departmentResult.childDept.isNotBlank()) {
                currentDepartment = Department(
                    id = departmentResult.childDept,
                    name = departmentResult.childDept,
                    clinicName = departmentResult.parentDept
                )
            }
        }

    suspend fun confirmTriage(caseId: String): TriageResultDto =
        apiClient.chat(ChatRequest(caseId = caseId, confirmed = true))

    suspend fun recommend(caseId: String): RecommendationResultDto =
        apiClient.recommend(RecommendRequest(caseId = caseId))

    suspend fun generateScript(caseId: String, recommendationId: String): ScriptResponseDto =
        apiClient.generateScript(ScriptRequest(caseId = caseId, recommendationId = recommendationId))

    suspend fun synthesizeSpeech(text: String, lang: String): VoiceTtsResponseDto =
        apiClient.tts(TtsRequest(text = text, lang = lang))

    suspend fun voiceChat(
        audioBytes: ByteArray,
        caseId: String?,
        lang: String,
        confirmed: Boolean = false
    ): VoiceChatResponseDto =
        apiClient.voiceChat(
            audioBytes = audioBytes,
            caseId = caseId,
            lang = lang,
            confirmed = confirmed
        )

    fun getAllHistory(): Flow<List<History>> = flow {
        loadHistoryIfNeeded()
        delay(100)
        emit(historyItems.toList())
    }

    fun getHistoryById(id: String): History? {
        loadHistoryIfNeeded()
        return historyItems.find { it.id == id }
    }

    fun loadHistoryIntoCurrentChat(id: String): History? {
        val history = getHistoryById(id) ?: return null
        chatMessages.clear()
        chatMessages.addAll(history.chatMessages)
        return history
    }

    fun saveToHistory(history: History) {
        loadHistoryIfNeeded()
        historyItems.removeAll { it.id == history.id }
        historyItems.add(0, history)
        persistHistory()
    }

    fun deleteHistory(id: String) {
        loadHistoryIfNeeded()
        historyItems.removeAll { it.id == id }
        persistHistory()
    }

    fun saveCurrentChatToHistory(
        historyId: String,
        summaryText: String,
        completed: Boolean,
        doctorName: String? = null
    ) {
        val history = History(
            id = historyId,
            date = todayText(),
            typeTitle = if (completed) currentDepartment?.name ?: "掛號導引" else "AI 問診",
            summaryText = summaryText.ifBlank { "問診紀錄" },
            doctorName = doctorName,
            status = if (completed) HistoryStatus.COMPLETED else HistoryStatus.UNCOMPLETED,
            chatMessages = chatMessages.toList()
        )
        saveToHistory(history)
    }

    fun getChatMessages(): List<ChatMessage> = chatMessages

    fun addMessage(message: ChatMessage) {
        chatMessages.add(message)
    }

    fun clearChatMessages() {
        chatMessages.clear()
    }

    suspend fun analyzeSymptomWithAI(symptom: String): Department {
        delay(300)
        return when {
            symptom.contains("眼") || symptom.contains("eye", ignoreCase = true) -> departments[1]
            symptom.contains("發燒") || symptom.contains("感冒") || symptom.contains("fever", ignoreCase = true) -> departments[2]
            else -> departments[0]
        }.also { currentDepartment = it }
    }

    suspend fun getDoctorsByDepartment(deptName: String): List<Doctor> {
        delay(200)
        val department = departments.find {
            it.name.contains(deptName, ignoreCase = true) ||
                it.clinicName.contains(deptName, ignoreCase = true)
        } ?: currentDepartment ?: departments[0]
        return doctors.filter { it.departmentId == department.id }.ifEmpty { doctors }
    }

    fun setCurrentDepartment(department: Department) {
        currentDepartment = department
    }

    fun setCurrentDoctor(doctor: Doctor) {
        currentDoctor = doctor
        doctor.availableSlots.firstOrNull()?.let { slot ->
            currentDayOfWeek = slot.first
            currentTimeSlot = slot.second
        }
    }

    fun setCurrentTimeSlot(dayOfWeek: String, timeSlot: String) {
        currentDayOfWeek = dayOfWeek
        currentTimeSlot = timeSlot
    }

    fun getConfirmedAppointment(): Appointment {
        val department = currentDepartment ?: departments[0]
        val doctor = currentDoctor ?: doctors[0]
        return Appointment(
            id = "apt_${System.currentTimeMillis()}",
            date = todayText(),
            dayOfWeek = currentDayOfWeek,
            timeSlot = currentTimeSlot,
            department = department,
            doctor = doctor
        )
    }
}

private fun todayText(): String =
    SimpleDateFormat("yyyy/MM/dd", Locale.TAIWAN).format(Date())

private fun History.toJson(): JSONObject = JSONObject().apply {
    put("id", id)
    put("date", date)
    put("typeTitle", typeTitle)
    put("summaryText", summaryText)
    put("doctorName", doctorName)
    put("status", status.name)
    put("chatMessages", JSONArray().also { array ->
        chatMessages.forEach { message ->
            array.put(JSONObject().apply {
                put("id", message.id)
                put("content", message.content)
                put("sender", message.sender.name)
                put("timestamp", message.timestamp)
            })
        }
    })
}

private fun JSONObject.toHistory(): History {
    val messages = optJSONArray("chatMessages")?.let { array ->
        (0 until array.length()).mapNotNull { index ->
            array.optJSONObject(index)?.let { item ->
                ChatMessage(
                    id = item.optString("id"),
                    content = item.optString("content"),
                    sender = runCatching {
                        MessageSender.valueOf(item.optString("sender"))
                    }.getOrDefault(MessageSender.AI),
                    timestamp = item.optLong("timestamp", System.currentTimeMillis())
                )
            }
        }
    } ?: emptyList()

    return History(
        id = optString("id"),
        date = optString("date"),
        typeTitle = optString("typeTitle", "AI 問診"),
        summaryText = optString("summaryText", "問診紀錄"),
        doctorName = if (isNull("doctorName")) null else optString("doctorName"),
        status = runCatching {
            HistoryStatus.valueOf(optString("status"))
        }.getOrDefault(HistoryStatus.UNCOMPLETED),
        chatMessages = messages
    )
}
