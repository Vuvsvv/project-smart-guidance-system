package com.example.medicalaiguidance.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.medicalaiguidance.model.Doctor
import com.example.medicalaiguidance.model.DoctorProfile
import com.example.medicalaiguidance.network.RecommendationItemDto
import com.example.medicalaiguidance.repository.MedicalRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// 定義 UI 的狀態包裝，資管系專業作法：把載入中、成功、錯誤分開
sealed interface DoctorUiState {
    object Loading : DoctorUiState
    data class Success(
        val doctors: List<Doctor>,
        val recommendations: List<RecommendationItemDto> = emptyList(),
        val mode: DoctorRecommendationMode = DoctorRecommendationMode.TIME_FIRST,
        val profiledDoctorNames: Set<String> = emptySet(),
        val departmentLabel: String? = null
    ) : DoctorUiState
    data class Error(val message: String) : DoctorUiState
}

enum class DoctorRecommendationMode {
    TIME_FIRST,
    SPECIALTY_FIRST
}

class DoctorViewModel(
    private val repository: MedicalRepository = MedicalRepository() // 實際專案建議用 DI 注入
) : ViewModel() {

    // 1️⃣ 管控醫生列表的狀態
    private val _uiState = MutableStateFlow<DoctorUiState>(DoctorUiState.Loading)
    val uiState: StateFlow<DoctorUiState> = _uiState.asStateFlow()

    // 2️⃣ 管控 BottomSheet 的顯示狀態與目前選中的醫生
    private val _selectedDoctor = MutableStateFlow<Doctor?>(null)
    val selectedDoctor: StateFlow<Doctor?> = _selectedDoctor.asStateFlow()

    private val _selectedDoctorProfile = MutableStateFlow<DoctorProfile?>(null)
    val selectedDoctorProfile: StateFlow<DoctorProfile?> = _selectedDoctorProfile.asStateFlow()

    private val _showBottomSheet = MutableStateFlow(false)
    val showBottomSheet: StateFlow<Boolean> = _showBottomSheet.asStateFlow()

    init {
        loadDoctorRecommendations()
    }

    fun loadDoctorRecommendations() {
        viewModelScope.launch {
            _uiState.value = DoctorUiState.Loading
            val mode = if (repository.isSpecialtyPriority()) {
                DoctorRecommendationMode.SPECIALTY_FIRST
            } else {
                DoctorRecommendationMode.TIME_FIRST
            }
            try {
                val caseId = repository.getCurrentCaseId()
                if (caseId != null) {
                    val result = repository.recommend(caseId)
                    val recommendations = if (mode == DoctorRecommendationMode.SPECIALTY_FIRST) {
                        result.recommendations.specialtyFirst
                    } else {
                        result.recommendations.timeFirst
                    }
                    if (recommendations.isNotEmpty()) {
                        _uiState.value = DoctorUiState.Success(
                            doctors = emptyList(),
                            recommendations = recommendations,
                            mode = mode,
                            profiledDoctorNames = profiledDoctorNamesFromRecommendations(recommendations),
                            departmentLabel = repository.getCurrentDepartmentLabel()
                        )
                        return@launch
                    }
                }
                val doctorList = repository.getDoctorsByDepartment("")
                _uiState.value = DoctorUiState.Success(
                    doctors = doctorList,
                    mode = mode,
                    profiledDoctorNames = profiledDoctorNamesFromDoctors(doctorList),
                    departmentLabel = repository.getCurrentDepartmentLabel()
                )
            } catch (e: Exception) {
                runCatching {
                    val doctorList = repository.getDoctorsByDepartment("")
                    _uiState.value = DoctorUiState.Success(
                        doctors = doctorList,
                        mode = mode,
                        profiledDoctorNames = profiledDoctorNamesFromDoctors(doctorList),
                        departmentLabel = repository.getCurrentDepartmentLabel()
                    )
                }.getOrElse {
                    _uiState.value = DoctorUiState.Error(e.message ?: "未知錯誤")
                }
            }
        }
    }

    fun fetchDoctors(departmentName: String) {
        viewModelScope.launch {
            _uiState.value = DoctorUiState.Loading
            try {
                val doctorList = repository.getDoctorsByDepartment(departmentName)
                _uiState.value = DoctorUiState.Success(
                    doctors = doctorList,
                    profiledDoctorNames = profiledDoctorNamesFromDoctors(doctorList),
                    departmentLabel = repository.getCurrentDepartmentLabel()
                )
            } catch (e: Exception) {
                _uiState.value = DoctorUiState.Error(e.message ?: "未知錯誤")
            }
        }
    }

    // 當使用者點擊「顯示專長」的箭頭
    fun onDoctorSpecialtyClick(doctor: Doctor) {
        _selectedDoctor.value = doctor
        _selectedDoctorProfile.value = repository.getDoctorProfileByName(doctor.name)
        _showBottomSheet.value = true
    }

    fun onRecommendationSpecialtyClick(recommendation: RecommendationItemDto) {
        val profile = repository.getDoctorProfileByName(recommendation.doctor)
        _selectedDoctor.value = Doctor(
            id = recommendation.recommendationId,
            name = recommendation.doctor.ifBlank { profile?.name ?: "推薦醫師" },
            departmentId = recommendation.childDept,
            title = profile?.titles?.firstOrNull()
                ?: recommendation.childDept.ifBlank { "推薦醫師" },
            specialties = profile?.specialtyTags ?: recommendation.reasons,
            imageUrl = profile?.photoUrl,
            availableSlots = listOf(
                recommendation.date to recommendation.slot.ifBlank { recommendation.session }
            )
        )
        _selectedDoctorProfile.value = profile
        _showBottomSheet.value = true
    }

    // 關閉 BottomSheet
    fun dismissBottomSheet() {
        _showBottomSheet.value = false
        _selectedDoctor.value = null
        _selectedDoctorProfile.value = null
    }

    // 當使用者決定選取這位醫生，準備前往確認頁
    fun selectDoctorAndNavigate(doctor: Doctor, onNavigate: () -> Unit) {
        // 將選擇的醫生暫存回 Repository，方便下一頁 ConfirmScreen 讀取
        repository.setCurrentDoctor(doctor)
        onNavigate()
    }

    fun selectRecommendationAndNavigate(
        recommendation: RecommendationItemDto,
        onNavigate: () -> Unit
    ) {
        repository.setCurrentRecommendation(recommendation)
        onNavigate()
    }

    private fun profiledDoctorNamesFromDoctors(doctors: List<Doctor>): Set<String> =
        doctors.mapNotNull { doctor ->
            doctor.name.takeIf { repository.getDoctorProfileByName(it) != null }
        }.toSet()

    private fun profiledDoctorNamesFromRecommendations(
        recommendations: List<RecommendationItemDto>
    ): Set<String> =
        recommendations.mapNotNull { recommendation ->
            recommendation.doctor.takeIf { repository.getDoctorProfileByName(it) != null }
        }.toSet()
}
