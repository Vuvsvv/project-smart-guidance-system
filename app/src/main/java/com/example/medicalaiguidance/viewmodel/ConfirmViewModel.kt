package com.example.medicalaiguidance.viewmodel

import androidx.lifecycle.ViewModel
import com.example.medicalaiguidance.model.Appointment
import com.example.medicalaiguidance.repository.MedicalRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class ConfirmViewModel(
    private val repository: MedicalRepository = MedicalRepository()
) : ViewModel() {

    private val _appointmentInfo = MutableStateFlow<Appointment?>(null)
    val appointmentInfo: StateFlow<Appointment?> = _appointmentInfo.asStateFlow()

    init {
        loadConfirmedAppointment()
    }

    fun loadConfirmedAppointment() {
        // 從 Repository 拿到組合好的預約單（包含剛剛 Chat 選的科別、Doctor 頁選的醫生）
        _appointmentInfo.value = repository.getConfirmedAppointment()
    }
}