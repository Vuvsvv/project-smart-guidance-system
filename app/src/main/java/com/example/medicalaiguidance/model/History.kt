package com.example.medicalaiguidance.model

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MedicalServices
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.ui.graphics.vector.ImageVector

// 對應設計圖上的標籤狀態
enum class HistoryStatus {
    ALL,        // 全部
    COMPLETED,  // 已完成
    UNCOMPLETED // 未完成（評估中）
}

data class History(
    val id: String,
    val date: String,                // 例如：2026年6月3日
    val typeTitle: String,           // 標題，例如："AI 症狀評估" 或 "一般骨科"
    val summaryText: String,         // 摘要，例如："我這幾天上下樓梯，膝蓋好痛喔"
    val doctorName: String? = null,  // 醫生姓名（未完成時為 null）
    val status: HistoryStatus,       // 目前狀態
    val chatMessages: List<ChatMessage> = emptyList() // 核心：儲存當初這場對話的所有對話紀錄
) {
    // 根據標題動態決定 UI 要顯示哪種圖標
    val icon: ImageVector
        get() = when {
            typeTitle.contains("AI") -> Icons.Filled.MedicalServices
            typeTitle.contains("眼科") -> Icons.Filled.Visibility
            typeTitle.contains("心臟") -> Icons.Filled.Favorite
            else -> Icons.Filled.MedicalServices
        }
}