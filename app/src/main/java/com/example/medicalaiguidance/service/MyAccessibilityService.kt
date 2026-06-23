package com.example.medicalaiguidance.service

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.util.Log

class MyAccessibilityService : AccessibilityService() {
    companion object {
        private var pendingDepartment: String? = null
        private var pendingClinic: String? = null
        private var pendingDoctor: String? = null
        private var pendingTime: String? = null
        private var shouldUpdateScript = false
        private var forceReset = false

        fun updateTarget(department: String, clinic: String, doctor: String, time: String) {
            pendingDepartment = department
            pendingClinic = clinic
            pendingDoctor = doctor
            pendingTime = time
            shouldUpdateScript = true
        }

        fun resetTarget() {
            forceReset = true
            pendingDepartment = null
            pendingClinic = null
            pendingDoctor = null
            pendingTime = null
            shouldUpdateScript = false
        }
    }

    private var overlay: OverlayManager? = null
    private var currentStepIndex = 0
    private var isDialogOpen = false
    private var script = listOf<String>()

    private val calendar = java.util.Calendar.getInstance()
    private val rocYear = calendar.get(java.util.Calendar.YEAR) - 1911
    private val month = calendar.get(java.util.Calendar.MONTH) + 1
    private val day = calendar.get(java.util.Calendar.DAY_OF_MONTH)
    //private val doctorSearchTabs = listOf("依醫生姓名", "依醫師姓名")

    override fun onServiceConnected() {
        super.onServiceConnected()
        overlay = OverlayManager(this)
    }

    private fun generateDynamicScript(department: String, clinic: String, doctor: String, time: String) {
        script = listOf(
            "行動掛號", "繼續掛號", "依門診科別",
            department, clinic, "選擇看診時間", doctor,
            "填寫個人資料", "請輸入身分證號", "請輸入病患姓名",
            "民國${rocYear}年", "${month}月", "${day}日", "確認送出"
        )
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return

        if (forceReset) {
            script = emptyList()
            currentStepIndex = 0
            overlay?.hide()
            forceReset = false
        }

        if (shouldUpdateScript) {
            generateDynamicScript(
                pendingDepartment ?: "", pendingClinic ?: "",
                pendingDoctor ?: "", pendingTime ?: ""
            )
            currentStepIndex = 0
            shouldUpdateScript = false
        }

        val packageName = event.packageName?.toString() ?: rootInActiveWindow?.packageName?.toString() ?: ""
        if (packageName.contains(this.packageName)) return

        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val className = event.className?.toString() ?: ""
            isDialogOpen = className.contains("Dialog") || className.contains("PopupWindow") || className.contains("Menu")
        }

        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||
            event.eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) {
            val root = rootInActiveWindow ?: return
            if (script.isNotEmpty()) handleStep(root)
        }
    }

    override fun onInterrupt() { overlay?.hide() }
    override fun onDestroy() {
        super.onDestroy()
        overlay?.hide()
    }
    private fun handleStep(node: AccessibilityNodeInfo) {
        val allNodes = findAllTextNodes(node)
        if (allNodes.isEmpty()) {
            overlay?.hide()
            return
        }

        if (currentStepIndex >= script.size) return

        val currentKeyword = script[currentStepIndex]
        val yearCount = allNodes.count { it.text.contains("民國") }
        val monthCount = allNodes.count { it.text.contains("月") && it.text.length < 5 }
        val dayCount = allNodes.count { it.text.contains("日") && it.text.length < 5 }
        val isDateStep = currentKeyword.contains("年") || currentKeyword.contains("月") || currentKeyword.contains("日")

        if (isDateStep && (isDialogOpen || yearCount > 3 || monthCount > 3 || dayCount > 3)) {
            overlay?.hide()
            return
        }

        val isWaitStep = currentKeyword.contains("請輸入") || isDateStep

        if (!isWaitStep && currentStepIndex + 1 < script.size) {
            val nextKeyword = script[currentStepIndex + 1]
            val nextNode = allNodes.find { it.text.contains(nextKeyword) }
            if (nextNode != null) currentStepIndex++
        }

        val finalKeyword = script[currentStepIndex]
        val currentTarget = allNodes.find { it.text.contains(finalKeyword) }

        if (currentTarget != null) {
            highlight(currentTarget.rect, "步驟 ${currentStepIndex + 1}: 請操作 $finalKeyword")
        } else {
            var foundFuture = false
            for (i in 1..2) {
                if (currentStepIndex + i < script.size) {
                    val futureKeyword = script[currentStepIndex + i]
                    val futureNode = allNodes.find { it.text.contains(futureKeyword) }
                    if (futureNode != null) {
                        currentStepIndex += i
                        highlight(futureNode.rect, "跳躍到步驟 ${currentStepIndex + 1}: $futureKeyword")
                        foundFuture = true
                        break
                    }
                }
            }
            if (foundFuture) return

            if (currentStepIndex > 0) {
                val prevKeyword = script[currentStepIndex - 1]
                val prevNode = allNodes.find { it.text.contains(prevKeyword) }
                if (prevNode != null) {
                    currentStepIndex--
                    highlight(prevNode.rect, "退回步驟 ${currentStepIndex + 1}: $prevKeyword")
                    return
                }
            }
            if (!isDialogOpen) overlay?.hide()
        }
    }
    // ─── 精修核心：findBestMatch ───
    private fun findBestMatch(nodes: List<NodeData>, keyword: String): NodeData? {
        if (keyword.isBlank()) return null

        if (keyword == "行動掛號") {
            return nodes.find { it.text.contains(keyword) }
        }

        // 找出所有包含關鍵字的節點
        val matches = nodes.filter { it.text.contains(keyword) }
        if (matches.isEmpty()) return null

        if (keyword == "依門診科別") {
            val exactTab = matches
                //.filterNot { node -> doctorSearchTabs.any { tab -> node.text.contains(tab) } }
                .minWithOrNull(
                    compareBy<NodeData> { if (it.text.trim() == keyword) 0 else 1 }
                        .thenBy { it.text.length }
                        .thenBy { it.rect.width() * it.rect.height() }
                )
            if (exactTab != null) return exactTab

            val combinedTabs = matches
                //.filter { node -> doctorSearchTabs.any { tab -> node.text.contains(tab) } }
                .minByOrNull { it.rect.width() * it.rect.height() }
            return combinedTabs?.let { node ->
                val leftTabRect = Rect(
                    node.rect.left,
                    node.rect.top,
                    node.rect.left + node.rect.width() / 2,
                    node.rect.bottom
                )
                NodeData(keyword, leftTabRect)
            }
        }

        // 如果遇到容易被長段落注意事項干擾的關鍵字，加入嚴格的字數限制篩選 (避免抓到內文說明)
        val filteredMatches = if (keyword == "選擇看診時間 / 醫師" || keyword.length >= 6) {
            matches.filter { it.text.length <= keyword.length + 6 } // 限制抓到的節點字數長度不能比關鍵字多太多
        } else {
            matches
        }

        if (filteredMatches.isEmpty()) return null

        // 依權重排序：完全符合(Trim後)優先 > 字串長度短優先（排除長文章） > 面積小優先（避免抓到外層Layout）
        val bestMatch = filteredMatches.minWithOrNull(
            compareBy<NodeData> { if (it.text.trim() == keyword) 0 else 1 }
                .thenBy { it.text.length }
                .thenBy { it.rect.width() * it.rect.height() }
        )

        return if (keyword == "選擇看診時間 / 醫師") {
            bestMatch?.withCompactTopBounds()
        } else {
            bestMatch
        }
    }

    private fun NodeData.withCompactTopBounds(): NodeData {
        if (rect.height() <= 300) return this

        val compactHeight = 96
        return copy(
            rect = Rect(
                rect.left,
                rect.top,
                rect.right,
                rect.top + compactHeight
            )
        )
    }

    private fun findAllTextNodes(root: AccessibilityNodeInfo): List<NodeData> {
        val result = mutableListOf<NodeData>()
        traverse(root, result)
        return result
    }

    private fun traverse(node: AccessibilityNodeInfo?, list: MutableList<NodeData>) {
        if (node == null) return

        val nodeText = node.text?.toString() ?: ""
        val viewId = node.viewIdResourceName
        if (nodeText.isNotEmpty()) {
            Log.d("vgh_id_detect", "抓到文字了: $nodeText | ID是: $viewId")
        }

        val rawText = node.text?.toString() ?: ""
        val rawDesc = node.contentDescription?.toString() ?: ""
        val rawHint = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            node.hintText?.toString() ?: ""
        } else { "" }

        val isFilled = rawText.isNotEmpty() && !rawText.contains("請輸入") && rawText != rawHint && rawText != rawDesc
        val combinedText = if (isFilled) rawText else "$rawText $rawDesc $rawHint".trim()

        if (combinedText.isNotEmpty()) {
            val rect = android.graphics.Rect()
            node.getBoundsInScreen(rect)
            if (rect.width() > 0 && rect.height() > 0) {
                list.add(NodeData(combinedText, rect))
            }
        }
        for (i in 0 until node.childCount) traverse(node.getChild(i), list)
    }

    private fun highlight(rect: Rect, msg: String) {
        val targetRect = if (rect.height() > 800) {
            Rect(rect.centerX() - 150, rect.centerY() - 50, rect.centerX() + 150, rect.centerY() + 50)
        } else rect
        overlay?.show(targetRect)
    }
}

data class NodeData(val text: String, val rect: Rect)