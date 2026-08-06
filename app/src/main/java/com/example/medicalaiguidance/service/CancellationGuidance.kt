package com.example.medicalaiguidance.service

import android.content.res.Resources
import android.graphics.Rect
import android.util.Log

/** 取消掛號紅框導引的專屬步驟與按鈕定位規則。 */
internal object CancellationGuidance {
    val script = listOf("掛號查詢", "請輸入身分證號", "取消")

    fun isDataEntryStep(keyword: String): Boolean = keyword == "請輸入身分證號"

    fun findTarget(nodes: List<NodeData>, keyword: String): NodeData? {
        val visibleNodes = nodes.filter { it.isOnScreen() }
        return when (keyword) {
            "掛號查詢" -> visibleNodes.firstOrNull { hasMatchText(it, keyword) }
            "請輸入身分證號" -> visibleNodes.firstOrNull {
                hasMatchText(it, keyword) || hasMatchText(it, "身分證號")
            }
            "取消", "推播", "加入行事曆" -> findBottomButton(nodes, keyword)
            else -> null
        }
    }

    private fun hasMatchText(node: NodeData, keyword: String): Boolean {
        val textNoSpace = node.text.replace(" ", "")
        val descNoSpace = (node.contentDescription ?: "").replace(" ", "")
        if (textNoSpace.isBlank() && descNoSpace.isBlank()) return false
        return textNoSpace.contains(keyword) || descNoSpace.contains(keyword)
    }

    private fun findBottomButton(allNodes: List<NodeData>, keyword: String): NodeData? {
        val screenWidth = Resources.getSystem().displayMetrics.widthPixels
        val screenHeight = Resources.getSystem().displayMetrics.heightPixels

        // 策略一：常規文字比對 (保留此邏輯，若未來 App 更新加上了文字，依然能正常運作)
        val textCandidates = allNodes.filter { hasMatchText(it, keyword) }
        val textMatch = textCandidates.filter { it.rect.centerY() > screenHeight * 0.4 }.maxByOrNull { it.rect.bottom }
        if (textMatch != null) {
            Log.d("vgh_id_detect", "透過文字找到按鈕 [$keyword]: ${textMatch.rect.toShortString()}")
            return textMatch
        }

        // 策略二：空間定位法 (專門針對隱藏文字的按鈕)
        // 1. 先找到畫面上的錨點 (掛號單的內容，例如「預約號碼」或「初診先報到」)
        val anchorNode = allNodes.find { it.text.contains("預約號碼") || it.text.contains("初診先報到") }

        if (anchorNode != null) {
            // 2. 找出錨點「下方」所有可點擊的元件
            val clickableButtons = allNodes.filter { node ->
                node.isClickable &&
                        node.rect.top >= anchorNode.rect.bottom - 40 && // 確保在錨點下方 (容許一點誤差)
                        node.rect.centerY() > screenHeight * 0.4 &&
                        node.rect.width() in 50..(screenWidth / 2) // 大小像個按鈕，排除整個大背景
            }.sortedBy { it.rect.left } // 依照 X 座標由左至右排序

            Log.d("vgh_id_detect", "空間定位法 - 找到錨點: ${anchorNode.text}, 下方可點擊按鈕數量: ${clickableButtons.size}")

            // 3. 根據畫面截圖推斷位置：左邊是行事曆，中間是推播，右邊是取消
            val targetNode = when (keyword) {
                "加入行事曆" -> clickableButtons.firstOrNull() // 取最左邊
                "取消" -> clickableButtons.lastOrNull() // 取最右邊
                "推播" -> if (clickableButtons.size >= 3) clickableButtons[1] else null // 取中間
                else -> null
            }

            if (targetNode != null) {
                Log.d("vgh_id_detect", "透過空間定位法成功鎖定 [$keyword]: ${targetNode.rect.toShortString()}")
                return targetNode
            }
        }

        Log.d("vgh_id_detect", "找不到按鈕 [$keyword]，請確認畫面是否已載入完成。")
        return null
    }
}

internal fun NodeData.isOnScreen(): Boolean {
    val screenWidth = Resources.getSystem().displayMetrics.widthPixels
    val screenHeight = Resources.getSystem().displayMetrics.heightPixels
    return rect.width() > 0 && rect.height() > 0 &&
            rect.right > 0 && rect.left < screenWidth &&
            rect.bottom > 0 && rect.top < screenHeight
}