package com.example.medicalaiguidance.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.medicalaiguidance.model.Doctor
import com.example.medicalaiguidance.repository.MedicalRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// 定義 UI 的狀態包裝，資管系專業作法：把載入中、成功、錯誤分開
sealed interface DoctorUiState {
    object Loading : DoctorUiState
    data class Success(val doctors: List<Doctor>) : DoctorUiState
    data class Error(val message: String) : DoctorUiState
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

    private val _showBottomSheet = MutableStateFlow(false)
    val showBottomSheet: StateFlow<Boolean> = _showBottomSheet.asStateFlow()

    init {
        // 初始化時，根據 AI 辨識出的科別撈取醫生（這裡我們先預設撈取骨科相關醫生）
        fetchDoctors("骨科")
    }

    fun fetchDoctors(departmentName: String) {
        viewModelScope.launch {
            _uiState.value = DoctorUiState.Loading
            try {
                val doctorList = repository.getDoctorsByDepartment(departmentName)
                _uiState.value = DoctorUiState.Success(doctorList)
            } catch (e: Exception) {
                _uiState.value = DoctorUiState.Error(e.message ?: "未知錯誤")
            }
        }
    }

    // 當使用者點擊「顯示專長」的箭頭
    fun onDoctorSpecialtyClick(doctor: Doctor) {
        _selectedDoctor.value = doctor
        _showBottomSheet.value = true
    }

    // 關閉 BottomSheet
    fun dismissBottomSheet() {
        _showBottomSheet.value = false
        _selectedDoctor.value = null
    }

    // 當使用者決定選取這位醫生，準備前往確認頁
    fun selectDoctorAndNavigate(doctor: Doctor, onNavigate: () -> Unit) {
        // 將選擇的醫生暫存回 Repository，方便下一頁 ConfirmScreen 讀取
        repository.setCurrentDoctor(doctor)
        onNavigate()
    }
}