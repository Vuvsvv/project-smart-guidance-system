package com.example.medicalaiguidance.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.medicalaiguidance.model.History
import com.example.medicalaiguidance.repository.MedicalRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class HomeViewModel(
    private val repository: MedicalRepository = MedicalRepository()
) : ViewModel() {

    private val _recentHistory = MutableStateFlow<List<History>>(emptyList())
    val recentHistory: StateFlow<List<History>> = _recentHistory.asStateFlow()

    init {
        fetchRecentHistory()
    }

    fun fetchRecentHistory() {
        viewModelScope.launch {
            // 取得所有歷史紀錄，並只取前 2 筆作為首頁的「近期紀錄」
            repository.getAllHistory().collect { list ->
                _recentHistory.value = list.take(2)
            }
        }
    }
}