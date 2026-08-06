package com.example.medicalaiguidance.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.medicalaiguidance.model.History
import com.example.medicalaiguidance.model.HistoryStatus
import com.example.medicalaiguidance.repository.MedicalRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

sealed interface HistoryUiState {
    object Loading : HistoryUiState
    data class Success(val filteredHistory: List<History>) : HistoryUiState
    data class Error(val message: String) : HistoryUiState
}

class HistoryViewModel(
    private val repository: MedicalRepository = MedicalRepository()
) : ViewModel() {
    private val _allHistoryList = MutableStateFlow<List<History>>(emptyList())

    private val _selectedTab = MutableStateFlow(0)
    val selectedTab: StateFlow<Int> = _selectedTab.asStateFlow()

    private val _uiState = MutableStateFlow<HistoryUiState>(HistoryUiState.Loading)
    val uiState: StateFlow<HistoryUiState> = _uiState.asStateFlow()

    init {
        loadHistoryData()
    }

    fun loadHistoryData() {
        viewModelScope.launch {
            _uiState.value = HistoryUiState.Loading
            repository.getAllHistory()
                .catch { error ->
                    _uiState.value = HistoryUiState.Error(error.message ?: "無法載入歷史紀錄")
                }
                .collect { list ->
                    _allHistoryList.value = list
                    filterHistoryData()
                }
        }
    }

    fun onTabSelected(index: Int) {
        _selectedTab.value = index
        filterHistoryData()
    }

    fun deleteHistory(id: String) {
        repository.deleteHistory(id)
        _allHistoryList.value = _allHistoryList.value.filterNot { it.id == id }
        filterHistoryData()
    }

    // 新增：取消掛號邏輯
    fun cancelRegistration(id: String) {
        viewModelScope.launch {
            // 更新本地資料狀態（將該紀錄轉為未完成，並清空醫師）
            _allHistoryList.value = _allHistoryList.value.map { history ->
                if (history.id == id) {
                    history.copy(
                        status = HistoryStatus.UNCOMPLETED,
                        doctorName = null
                    )
                } else {
                    history
                }
            }
            filterHistoryData()
        }
    }

    private fun filterHistoryData() {
        val filtered = when (_selectedTab.value) {
            1 -> _allHistoryList.value.filter { it.status == HistoryStatus.COMPLETED }
            2 -> _allHistoryList.value.filter { it.status == HistoryStatus.UNCOMPLETED }
            else -> _allHistoryList.value
        }
        _uiState.value = HistoryUiState.Success(filtered)
    }
}