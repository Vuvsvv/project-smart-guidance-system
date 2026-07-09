package com.example.medicalaiguidance.service

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.util.Log

class MyAccessibilityService : AccessibilityService() {
    companion object {
        private const val VGH_PACKAGE_NAME = "tw.com.bicom.VGHTPE"
        private const val SCROLL_HINT_GRACE_MS = 800L

        private var pendingDepartment: String? = null
        private var pendingClinic: String? = null
        private var pendingDoctor: String? = null
        private var pendingDate: String? = null
        private var pendingTimeSlot: String? = null
        private var shouldUpdateScript = false
        private var forceReset = false

        fun updateTarget(
            department: String,
            clinic: String,
            doctor: String,
            date: String,
            timeSlot: String = ""
        ) {
            pendingDepartment = department
            pendingClinic = clinic
            pendingDoctor = doctor
            pendingDate = date
            pendingTimeSlot = timeSlot
            shouldUpdateScript = true
        }

    }

    private var overlay: OverlayManager? = null
    private var currentStepIndex = 0
    private var isDialogOpen = false
    private var script = listOf<String>()
    private var lastHighlightAt = 0L
    private var lastScrollHintAt = 0L
    private var waitingForPersonalDataExit = false
    private var hasLeftVghApp = false
    private var stepEnteredAt = 0L
    private var trackedStepIndex = 0

    private val calendar = java.util.Calendar.getInstance()
    private val rocYear = calendar.get(java.util.Calendar.YEAR) - 1911
    private val month = calendar.get(java.util.Calendar.MONTH) + 1
    private val day = calendar.get(java.util.Calendar.DAY_OF_MONTH)

    override fun onServiceConnected() {
        super.onServiceConnected()
        overlay = OverlayManager(this)
    }

    private fun generateDynamicScript(department: String, clinic: String, doctor: String, date: String) {
        val appointmentDay = date.toAppointmentDayText()
        script = listOf(
            "行動掛號", "繼續掛號", "依門診科別",
            department, clinic, "選擇看診時間", appointmentDay, doctor,
            "填寫個人資料", "請輸入身分證號", "請輸入病患姓名",
            "民國${rocYear}年", "${month}月", "${day}日", "確認送出"
        )
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return

        if (forceReset) {
            script = emptyList()
            resetInteractionState("手動重設", hideOverlay = true)
            forceReset = false
        }

        if (shouldUpdateScript) {
            generateDynamicScript(
                pendingDepartment ?: "", pendingClinic ?: "",
                pendingDoctor ?: "", pendingDate ?: ""
            )
            resetInteractionState("更新測試目標", hideOverlay = true)
            shouldUpdateScript = false
        }

        val activePackageName = rootInActiveWindow?.packageName?.toString().orEmpty()
        val eventPackageName = event.packageName?.toString().orEmpty()
        if (activePackageName == VGH_PACKAGE_NAME) {
            if (hasLeftVghApp) {
                resetInteractionState("重新進入榮總App", hideOverlay = true)
                hasLeftVghApp = false
            }
            if (eventPackageName.isNotBlank() && eventPackageName != VGH_PACKAGE_NAME) {
                Log.d("vgh_id_detect", "忽略非榮總事件，前景仍是榮總 eventPackage=$eventPackageName")
            }
        } else if (activePackageName.isNotBlank()) {
            markLeftVghApp(activePackageName)
            Log.d("vgh_id_detect", "目前前景不是榮總App，隱藏紅框 package=$activePackageName")
            return
        } else if (eventPackageName.isNotBlank() && eventPackageName != VGH_PACKAGE_NAME &&
            event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
        ) {
            markLeftVghApp(eventPackageName)
            Log.d("vgh_id_detect", "離開榮總App，隱藏紅框 package=$eventPackageName")
            return
        }

        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val className = event.className?.toString() ?: ""
            isDialogOpen = className.contains("Dialog") || className.contains("PopupWindow") || className.contains("Menu")
        }

        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||
            event.eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED ||
            event.eventType == AccessibilityEvent.TYPE_VIEW_CLICKED ||
            event.eventType == AccessibilityEvent.TYPE_VIEW_SELECTED) {
            val root = rootInActiveWindow ?: return
            if (script.isNotEmpty()) handleStep(root)
        }
    }

    override fun onInterrupt() { overlay?.hide() }
    override fun onDestroy() {
        super.onDestroy()
        overlay?.hide()
    }

    private fun markLeftVghApp(packageName: String) {
        hasLeftVghApp = true
        overlay?.hide()
        Log.d("vgh_id_detect", "標記已離開榮總App package=$packageName")
    }

    private fun resetInteractionState(reason: String, hideOverlay: Boolean) {
        currentStepIndex = 0
        trackedStepIndex = 0
        stepEnteredAt = System.currentTimeMillis()
        isDialogOpen = false
        waitingForPersonalDataExit = false
        lastHighlightAt = 0L
        lastScrollHintAt = 0L
        if (hideOverlay) overlay?.hide()
        Log.d("vgh_id_detect", "重設紅框流程 reason=$reason")
    }

    private fun moveToStep(index: Int, reason: String) {
        val boundedIndex = index.coerceIn(0, script.lastIndex.coerceAtLeast(0))
        if (currentStepIndex == boundedIndex) return
        currentStepIndex = boundedIndex
        trackedStepIndex = boundedIndex
        stepEnteredAt = System.currentTimeMillis()
        Log.d("vgh_id_detect", "切換紅框步驟 index=$boundedIndex keyword=${script.getOrNull(boundedIndex)} reason=$reason")
    }

    private fun advanceStep(reason: String) {
        moveToStep(currentStepIndex + 1, reason)
    }

    private fun handleStep(node: AccessibilityNodeInfo) {
        if (trackedStepIndex != currentStepIndex) {
            trackedStepIndex = currentStepIndex
            stepEnteredAt = System.currentTimeMillis()
        }

        val allNodes = findAllTextNodes(node)
        if (allNodes.isEmpty()) {
            hideOverlayIfStable()
            return
        }

        if (currentStepIndex >= script.size) return

        val currentKeyword = script[currentStepIndex]
        val yearCount = allNodes.count { it.text.contains("民國") }
        val monthCount = allNodes.count { it.text.contains("月") && it.text.length < 5 }
        val dayCount = allNodes.count { it.text.contains("日") && it.text.length < 5 }
        val isCalendarDayStep = currentKeyword.isCalendarDayNumber()
        val isDateStep = currentKeyword.contains("年") || currentKeyword.contains("月") || currentKeyword.contains("日")

        if (isDateStep && (isDialogOpen || yearCount > 3 || monthCount > 3 || dayCount > 3)) {
            hideOverlayIfStable()
            return
        }

        if (isCalendarDayStep && currentStepIndex + 1 < script.size) {
            val nextKeyword = script[currentStepIndex + 1]
            val nextIsDoctor = nextKeyword.isPendingDoctorKeyword()
            val nextNode = if (nextIsDoctor) {
                findDoctorInSession(allNodes, nextKeyword)
            } else {
                findBestMatch(allNodes, nextKeyword)
            }
            if (nextNode != null && isTargetAppointmentDateSelected(allNodes, currentKeyword)) {
                advanceStep("日期已選且下一步出現")
            }
        }

        val isWaitStep = currentKeyword.contains("請輸入") || isDateStep || isCalendarDayStep

        if (!isWaitStep && currentStepIndex + 1 < script.size) {
            val nextKeyword = script[currentStepIndex + 1]
            if (nextKeyword.isCalendarDayNumber() && isClinicCalendarVisible(allNodes)) {
                overlay?.hide()
                advanceStep("進入行事曆頁，先隱藏舊紅框")
            } else {
            val nextNode = findBestMatch(allNodes, nextKeyword)
                if (nextNode != null) {
                    advanceStep("下一步目標已出現")
                }
            }
        }

        if (isDepartmentStep(script[currentStepIndex]) && isSubClinicPickerVisible(allNodes)) {
            advanceStep("子科別選單已開啟")
        }

        if (waitingForPersonalDataExit) {
            if (isPersonalDataFormVisible(allNodes)) {
                overlay?.hide()
                Log.d("vgh_id_detect", "等待使用者離開個資表單")
                return
            }
            waitingForPersonalDataExit = false
            Log.d("vgh_id_detect", "已離開個資表單，繼續確認送出步驟")
        }

        if (shouldEnterPersonalDataWaiting(allNodes)) {
            val submitIndex = script.indexOf("確認送出")
            if (submitIndex >= 0) moveToStep(submitIndex, "進入個資表單後等待確認送出")
            waitingForPersonalDataExit = true
            overlay?.hide()
            Log.d("vgh_id_detect", "已進入個資表單，等待使用者填完並離開")
            return
        }

        val finalKeyword = script[currentStepIndex]
        if (isPrivatePersonalDataStep(finalKeyword)) {
            val submitNode = findBestMatch(allNodes, "確認送出")
            if (submitNode != null) {
                moveToStep(script.indexOf("確認送出"), "個資段落跳到確認送出")
                highlight(submitNode.rect)
            } else {
                overlay?.hide()
                Log.d("vgh_id_detect", "個資輸入段落隱藏紅框 keyword=$finalKeyword")
            }
            return
        }

        if (finalKeyword.isCalendarDayNumber()) {
            val nextKeyword = script.getOrNull(currentStepIndex + 1)
            val nextIsDoctor = nextKeyword.isPendingDoctorKeyword()
            val nextNode = nextKeyword?.let {
                if (nextIsDoctor) findDoctorInSession(allNodes, it) else findBestMatch(allNodes, it)
            }
            if (isTargetAppointmentDateSelected(allNodes, finalKeyword)) {
                if (nextKeyword != null) advanceStep("日期已選，進入下一步")
                if (nextNode != null) {
                    highlight(nextNode.rect)
                } else if (nextIsDoctor && nextKeyword != null) {
                    showScrollHint("溫馨提醒：請往下滑找到「$nextKeyword」")
                } else {
                    overlay?.hide()
                }
                return
            }

            val calendarDayNode = findCalendarDayTarget(allNodes, finalKeyword)
            if (calendarDayNode != null) {
                highlight(calendarDayNode.rect)
            } else {
                overlay?.hide()
                Log.d("vgh_id_detect", "行事曆日期未找到，等待使用者選日期 keyword=$finalKeyword")
            }
            return
        }

        if (isDepartmentStep(finalKeyword)) {
            val departmentTarget = findDepartmentInReservationSection(
                nodes = allNodes,
                departmentName = finalKeyword,
                targetSection = ReservationSection.INITIAL
            )
            if (departmentTarget != null) {
                highlight(departmentTarget.rect)
            } else {
                showScrollHintWhenStepStable("溫馨提醒：請在初診預約找到「$finalKeyword」")
            }
            return
        }

        if (isClinicStep(finalKeyword)) {
            val clinicTarget = findExactVisibleTextNode(allNodes, finalKeyword)
            if (clinicTarget != null) {
                highlight(clinicTarget.rect)
            } else {
                showScrollHint("溫馨提醒：請往下滑找到「$finalKeyword」")
            }
            return
        }

        if (isDoctorStep(finalKeyword)) {
            val doctorTarget = findDoctorInSession(allNodes, finalKeyword)
            if (doctorTarget != null) {
                highlight(doctorTarget.rect)
            } else {
                showScrollHint("溫馨提醒：請往下滑找到「$finalKeyword」")
            }
            return
        }

        val currentTarget = findBestMatch(allNodes, finalKeyword)

        if (currentTarget != null) {
            highlight(currentTarget.rect)
        } else {
            if (finalKeyword == "確認送出") {
                overlay?.hide()
                Log.d("vgh_id_detect", "等待確認送出出現")
                return
            }

            if (isClinicStep(finalKeyword)) {
                showScrollHint("找不到「$finalKeyword」，請往下滑")
                hideOverlayIfStable()
                return
            }

            if (isDoctorStep(finalKeyword)) {
                showScrollHint("找不到「$finalKeyword」，請往下滑")
                hideOverlayIfStable()
                return
            }

            var foundFuture = false
            for (i in 1..2) {
                if (currentStepIndex + i < script.size) {
                    val futureKeyword = script[currentStepIndex + i]
                    val futureNode = findBestMatch(allNodes, futureKeyword)
                    if (futureNode != null) {
                        moveToStep(currentStepIndex + i, "找到後續步驟")
                        highlight(futureNode.rect)
                        foundFuture = true
                        break
                    }
                }
            }
            if (foundFuture) return

            if (currentStepIndex >= script.indexOf("請輸入身分證號")) {
                val prevKeyword = script[currentStepIndex - 1]
                val prevNode = findBestMatch(allNodes, prevKeyword)
                if (prevNode != null) {
                    moveToStep(currentStepIndex - 1, "回到前一步")
                    highlight(prevNode.rect)
                    return
                }
            }
            if (!isDialogOpen) hideOverlayIfStable()
        }
    }
    // ─── 精修核心：findBestMatch ───
    private fun findBestMatch(nodes: List<NodeData>, keyword: String): NodeData? {
        if (keyword.isBlank()) return null
        val visibleNodes = nodes.filter { it.isOnScreen() }

        if (keyword.isCalendarDayNumber()) {
            val calendarNumberNodes = visibleNodes
                .filter { node -> node.text.trim().toIntOrNull()?.let { it in 1..31 } == true }
            val calendarRows = calendarNumberNodes
                .groupBy { it.rect.centerY() / 40 }
                .values
                .filter { row -> row.size >= 3 }
                .flatten()
            val calendarTop = calendarRows.minOfOrNull { it.rect.top } ?: 180
            val calendarBottom = calendarRows.maxOfOrNull { it.rect.bottom } ?: 720

            val exactCalendarDayNodes = visibleNodes
                .filter { it.text.trim() == keyword }
                .filter { it.rect.centerY() in calendarTop..calendarBottom }

            val bestCalendarDay = exactCalendarDayNodes.minWithOrNull(
                compareBy<NodeData> { kotlin.math.abs(it.rect.centerY() - 520) }
                    .thenBy { it.rect.width() * it.rect.height() }
            )
            Log.d(
                "vgh_id_detect",
                "行事曆日期比對 keyword=$keyword top=$calendarTop bottom=$calendarBottom " +
                    "allNumbers=${calendarNumberNodes.map { "${it.text}:${it.rect.toShortString()}" }} " +
                    "candidates=${exactCalendarDayNodes.map { it.rect.toShortString() }} " +
                    "best=${bestCalendarDay?.rect?.toShortString()}"
            )
            return bestCalendarDay
        }

        if (keyword == "行動掛號") {
            return visibleNodes.find { it.text.contains(keyword) }
        }

        // 找出所有包含關鍵字的節點
        val matches = visibleNodes.filter { it.text.contains(keyword) }
        if (matches.isEmpty()) return null

        if (keyword == "依門診科別") {
            val screenWidth = android.content.res.Resources.getSystem().displayMetrics.widthPixels
            val exactTab = matches
                .filter { it.text.trim() == keyword }
                .filter { it.rect.centerX() < screenWidth / 2 }
                .minWithOrNull(
                    compareBy<NodeData> { it.text.length }
                        .thenBy { it.rect.width() * it.rect.height() }
                )
            if (exactTab != null) return exactTab

            val combinedTabs = matches
                .filter { it.rect.centerX() < screenWidth / 2 || it.rect.width() > screenWidth / 2 }
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

    private fun isClinicCalendarVisible(nodes: List<NodeData>): Boolean {
        val hasMonthTitle = nodes.any { it.text.contains("月") && it.text.contains("202") }
        val weekdayCount = nodes.count {
            it.text.trim() in setOf("週日", "週一", "週二", "週三", "週四", "週五", "週六")
        }
        val hasClinicSession = nodes.any {
            it.text.contains("上午診") || it.text.contains("下午診") || it.text.contains("晚上診")
        }
        return hasMonthTitle && weekdayCount >= 5 && hasClinicSession
    }

    private fun findCalendarDayTarget(nodes: List<NodeData>, dayText: String): NodeData? {
        val exactNode = findBestMatch(nodes, dayText)
        if (exactNode != null) return exactNode

        val inferredRect = inferCalendarDayRect(nodes, dayText.toIntOrNull() ?: return null)
        if (inferredRect != null) {
            Log.d("vgh_id_detect", "行事曆日期使用推算座標 keyword=$dayText rect=${inferredRect.toShortString()}")
            return NodeData(dayText, inferredRect)
        }
        return null
    }

    private fun isTargetAppointmentDateSelected(nodes: List<NodeData>, dayText: String): Boolean {
        val targetDay = dayText.toIntOrNull() ?: return false
        val visibleNodes = nodes.filter { it.isOnScreen() }
        val monthTitle = visibleNodes
            .filter { it.text.contains("月") && it.text.contains("202") }
            .minByOrNull { it.rect.top }

        val selectedTopCardDay = monthTitle?.let { title ->
            visibleNodes
                .filter { node -> node.text.trim().toIntOrNull()?.let { it in 1..31 } == true }
                .filter { it.rect.centerY() < title.rect.centerY() }
                .maxByOrNull { it.rect.height() * it.rect.width() }
                ?.text
                ?.trim()
                ?.toIntOrNull()
        }
        if (selectedTopCardDay != null) {
            val matched = selectedTopCardDay == targetDay
            Log.d(
                "vgh_id_detect",
                "行事曆目前選取日 topCard=$selectedTopCardDay target=$targetDay matched=$matched"
            )
            return matched
        }

        val selectedCalendarDay = visibleNodes
            .filter { it.isSelected }
            .mapNotNull { it.text.trim().toIntOrNull() }
            .firstOrNull { it in 1..31 }
        if (selectedCalendarDay != null) {
            val matched = selectedCalendarDay == targetDay
            Log.d(
                "vgh_id_detect",
                "行事曆目前選取日 selectedNode=$selectedCalendarDay target=$targetDay matched=$matched"
            )
            return matched
        }

        Log.d("vgh_id_detect", "行事曆目前選取日無法判斷 target=$targetDay")
        return false
    }

    private fun inferCalendarDayRect(nodes: List<NodeData>, targetDay: Int): Rect? {
        val visibleNodes = nodes.filter { it.isOnScreen() }
        val monthTitle = visibleNodes
            .filter { it.text.contains("月") && it.text.contains("202") }
            .minByOrNull { it.rect.top }
            ?: return null

        val weekdayLabels = setOf("週日", "週一", "週二", "週三", "週四", "週五", "週六")
        val weekdayRow = visibleNodes
            .filter { it.text.trim() in weekdayLabels }
            .filter { it.rect.top > monthTitle.rect.bottom }
            .filter { it.rect.top < monthTitle.rect.bottom + 220 }
            .groupBy { it.rect.centerY() / 50 }
            .values
            .maxByOrNull { row -> row.map { it.text.trim() }.distinct().size }
            ?: return null

        val weekdayByText = weekdayRow
            .groupBy { it.text.trim() }
            .mapValues { (_, nodesInColumn) ->
                nodesInColumn.minWithOrNull(
                    compareBy<NodeData> { it.rect.width() * it.rect.height() }
                        .thenBy { it.rect.top }
                )
            }
        val appointmentWeekdayNodes = listOf("週一", "週二", "週三", "週四", "週五", "週六")
            .map { label -> weekdayByText[label] ?: return null }

        val yearMonth = pendingDate.toYearMonthOrNull() ?: return null
        val dayOfWeek = dayOfWeekOfDate(yearMonth.first, yearMonth.second, targetDay)
        if (dayOfWeek == java.util.Calendar.SUNDAY) {
            Log.d("vgh_id_detect", "行事曆日期略過週日 keyword=$targetDay")
            return null
        }
        val firstDayColumn = firstDayColumnOfMonth(yearMonth.first, yearMonth.second)
        val zeroBasedIndex = firstDayColumn + targetDay - 1
        val row = zeroBasedIndex / 7
        val column = dayOfWeek - java.util.Calendar.MONDAY

        val xCenter = appointmentWeekdayNodes[column].rect.centerX()
        val weekdayBottom = weekdayRow.maxOf { it.rect.bottom }
        val numberNodes = visibleNodes
            .filter { node -> node.text.trim().toIntOrNull()?.let { it in 1..31 } == true }
            .filter { it.rect.top > weekdayBottom }

        val cellHeight = numberNodes
            .map { it.rect.centerY() }
            .distinct()
            .sorted()
            .zipWithNext { a, b -> b - a }
            .filter { it > 20 }
            .minOrNull() ?: 66
        val firstRowY = numberNodes
            .filter { it.text.trim().toIntOrNull() in 1..7 }
            .minOfOrNull { it.rect.centerY() }
            ?: (weekdayBottom + cellHeight)
        val yCenter = firstRowY + row * cellHeight
        val size = 58

        val screenWidth = android.content.res.Resources.getSystem().displayMetrics.widthPixels
        val screenHeight = android.content.res.Resources.getSystem().displayMetrics.heightPixels
        val rect = Rect(
            xCenter - size / 2,
            yCenter - size / 2,
            xCenter + size / 2,
            yCenter + size / 2
        )
        if (rect.left < 0 || rect.right > screenWidth || rect.top <= monthTitle.rect.bottom || rect.bottom > screenHeight) {
            return null
        }
        Log.d(
            "vgh_id_detect",
            "行事曆日期使用週一到週六推算 keyword=$targetDay row=$row column=$column rect=${rect.toShortString()}"
        )
        return rect
    }

    private fun isDepartmentStep(keyword: String): Boolean =
        pendingDepartment?.isNotBlank() == true &&
            keyword == pendingDepartment &&
            currentStepIndex == script.indexOf(pendingDepartment)

    private fun findDepartmentInReservationSection(
        nodes: List<NodeData>,
        departmentName: String,
        targetSection: ReservationSection
    ): NodeData? {
        val visibleNodes = nodes.filter { it.isOnScreen() }
        val departmentCandidates = visibleNodes.filter { node ->
            node.text.normalizedLabel() == departmentName.normalizedLabel()
        }.ifEmpty {
            visibleNodes.filter { node ->
                node.text.contains(departmentName) && node.text.length <= departmentName.length + 4
            }
        }
        if (departmentCandidates.isEmpty()) return null

        val reservationHeaders = visibleNodes
            .mapNotNull { node ->
                node.text.toReservationSectionOrNull()?.let { section -> node to section }
            }
            .sortedBy { it.first.rect.centerY() }

        if (reservationHeaders.isEmpty()) {
            Log.d("vgh_id_detect", "預約科別比對 department=$departmentName section=$targetSection headers=[] 使用一般科別比對")
            return departmentCandidates.bestDepartmentCandidate()
        }

        val candidatesInSection = departmentCandidates.filterByReservationSection(
            reservationHeaders = reservationHeaders,
            targetSection = targetSection
        )

        val best = candidatesInSection.bestDepartmentCandidate()
        Log.d(
            "vgh_id_detect",
            "預約科別比對 department=$departmentName section=$targetSection " +
                "headers=${reservationHeaders.map { "${it.second}:${it.first.rect.toShortString()}" }} " +
                "candidates=${departmentCandidates.map { it.rect.toShortString() }} " +
                "matched=${candidatesInSection.map { it.rect.toShortString() }} best=${best?.rect?.toShortString()}"
        )
        return best
    }

    private fun List<NodeData>.filterByReservationSection(
        reservationHeaders: List<Pair<NodeData, ReservationSection>>,
        targetSection: ReservationSection
    ): List<NodeData> =
        filter { candidate ->
            val nearestHeader = reservationHeaders
                .filter { it.first.rect.centerY() <= candidate.rect.centerY() }
                .maxByOrNull { it.first.rect.centerY() }
            nearestHeader?.second == targetSection
        }.ifEmpty {
            val targetHeader = reservationHeaders.firstOrNull { it.second == targetSection }?.first
            val nextHeader = targetHeader?.let { header ->
                reservationHeaders
                    .map { it.first }
                    .filter { it.rect.centerY() > header.rect.centerY() }
                    .minByOrNull { it.rect.centerY() }
            }
            if (targetHeader == null) {
                emptyList()
            } else {
                filter { candidate ->
                    candidate.rect.centerY() > targetHeader.rect.centerY() &&
                        (nextHeader == null || candidate.rect.centerY() < nextHeader.rect.centerY())
                }
            }
        }

    private fun List<NodeData>.bestDepartmentCandidate(): NodeData? =
        minWithOrNull(
            compareBy<NodeData> { it.rect.width() * it.rect.height() }
                .thenBy { it.rect.top }
        )

    private fun isSubClinicPickerVisible(nodes: List<NodeData>): Boolean {
        val nextKeyword = script.getOrNull(currentStepIndex + 1)
        if (nextKeyword != pendingClinic) return false
        if (nodes.none { it.text.trim() == "CANCEL" }) return false

        val currentDepartment = pendingDepartment ?: return false
        return nodes.any { node ->
            val text = node.text.trim()
            text != currentDepartment &&
                text.contains("科") &&
                !text.endsWith("系") &&
                text != "依門診科別"
        }
    }

    private fun isClinicStep(keyword: String): Boolean =
        pendingClinic?.isNotBlank() == true &&
            keyword == pendingClinic &&
            currentStepIndex == script.indexOf(pendingClinic)

    private fun isDoctorStep(keyword: String): Boolean =
        pendingDoctor?.isNotBlank() == true &&
            keyword == pendingDoctor &&
            currentStepIndex == script.indexOf(pendingDoctor)

    private fun String?.isPendingDoctorKeyword(): Boolean =
        pendingDoctor?.isNotBlank() == true && this == pendingDoctor

    private fun isPrivatePersonalDataStep(keyword: String): Boolean =
        keyword == "請輸入身分證號" ||
            keyword == "請輸入病患姓名" ||
            keyword == "民國${rocYear}年" ||
            keyword == "${month}月" ||
            keyword == "${day}日"

    private fun shouldEnterPersonalDataWaiting(nodes: List<NodeData>): Boolean {
        val personalStartIndex = script.indexOf("填寫個人資料")
        val submitIndex = script.indexOf("確認送出")
        if (personalStartIndex < 0 || submitIndex < 0) return false
        if (currentStepIndex < personalStartIndex || currentStepIndex >= submitIndex) return false
        return isPersonalDataFormVisible(nodes)
    }

    private fun isPersonalDataFormVisible(nodes: List<NodeData>): Boolean {
        val hasIdField = nodes.any { it.text.trim() == "身分證號" || it.text.trim() == "請輸入身分證號" }
        val hasNameField = nodes.any { it.text.trim() == "姓名" || it.text.trim() == "請輸入病患姓名" }
        val hasBirthdayField = nodes.any { it.text.trim() == "出生年月日" }
        return hasIdField && hasNameField && hasBirthdayField
    }

    private fun findExactVisibleTextNode(nodes: List<NodeData>, keyword: String): NodeData? =
        nodes.asSequence()
            .filter { it.isOnScreen() }
            .filter { it.text.trim() == keyword }
            .minWithOrNull(
                compareBy<NodeData> { it.rect.width() * it.rect.height() }
                    .thenBy { it.rect.top }
            )

    private fun findDoctorInSession(nodes: List<NodeData>, doctorName: String): NodeData? {
        val visibleNodes = nodes.filter { it.isOnScreen() }
        val doctorCandidates = visibleNodes
            .filter { it.text.contains(doctorName) }
            .filter { it.text.length <= doctorName.length + 12 }

        if (doctorCandidates.isEmpty()) return null

        val targetSession = pendingTimeSlot.toVisitSessionOrNull()
        if (targetSession.isNullOrBlank()) {
            return doctorCandidates.bestDoctorCandidate(doctorName)
        }

        val sessionHeaders = visibleNodes
            .mapNotNull { node -> node.text.toVisitSessionOrNull()?.let { session -> node to session } }
            .sortedBy { it.first.rect.centerY() }

        if (sessionHeaders.isEmpty()) {
            Log.d("vgh_id_detect", "醫師診別比對 doctor=$doctorName session=$targetSession headers=[] 使用一般醫師比對")
            return doctorCandidates.bestDoctorCandidate(doctorName)
        }

        val candidatesInSession = doctorCandidates.filter { candidate ->
            val nearestHeader = sessionHeaders
                .filter { it.first.rect.centerY() <= candidate.rect.centerY() }
                .maxByOrNull { it.first.rect.centerY() }
            nearestHeader?.second == targetSession
        }

        val best = candidatesInSession.bestDoctorCandidate(doctorName)
        Log.d(
            "vgh_id_detect",
            "醫師診別比對 doctor=$doctorName session=$targetSession " +
                "headers=${sessionHeaders.map { "${it.second}:${it.first.rect.toShortString()}" }} " +
                "candidates=${doctorCandidates.map { "${it.text}:${it.rect.toShortString()}" }} " +
                "matched=${candidatesInSession.map { it.rect.toShortString() }} best=${best?.rect?.toShortString()}"
        )
        return best
    }

    private fun List<NodeData>.bestDoctorCandidate(doctorName: String): NodeData? =
        minWithOrNull(
            compareBy<NodeData> { if (it.text.trim() == doctorName) 0 else 1 }
                .thenBy { it.text.length }
                .thenBy { it.rect.width() * it.rect.height() }
        )

    private fun showScrollHint(message: String) {
        val now = System.currentTimeMillis()
        if (now - lastScrollHintAt < 2500) return
        lastScrollHintAt = now
        lastHighlightAt = now
        overlay?.showMessage(message)
        Log.d("vgh_id_detect", "提示使用者滑動: $message")
    }

    private fun showScrollHintWhenStepStable(message: String) {
        val elapsed = System.currentTimeMillis() - stepEnteredAt
        if (elapsed < SCROLL_HINT_GRACE_MS) {
            Log.d("vgh_id_detect", "延後滑動提示 elapsed=${elapsed}ms message=$message")
            return
        }
        showScrollHint(message)
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
                list.add(NodeData(combinedText, rect, node.isSelected))
            }
        }
        for (i in 0 until node.childCount) traverse(node.getChild(i), list)
    }

    private fun highlight(rect: Rect) {
        lastHighlightAt = System.currentTimeMillis()
        val targetRect = if (rect.height() > 800) {
            Rect(rect.centerX() - 150, rect.centerY() - 50, rect.centerX() + 150, rect.centerY() + 50)
        } else rect
        overlay?.show(targetRect)
    }

    private fun hideOverlayIfStable() {
        val elapsed = System.currentTimeMillis() - lastHighlightAt
        if (elapsed < 1500) {
            Log.d("vgh_id_detect", "忽略暫態hide elapsed=${elapsed}ms")
            return
        }
        overlay?.hide()
    }

}

data class NodeData(val text: String, val rect: Rect, val isSelected: Boolean = false)

private enum class ReservationSection {
    INITIAL,
    RETURN_VISIT
}

private fun NodeData.isOnScreen(): Boolean {
    val screenWidth = android.content.res.Resources.getSystem().displayMetrics.widthPixels
    val screenHeight = android.content.res.Resources.getSystem().displayMetrics.heightPixels
    return rect.right > 0 &&
        rect.left < screenWidth &&
        rect.bottom > 0 &&
        rect.top < screenHeight
}

private fun String.toAppointmentDayText(): String {
    val trimmed = trim()
    if (trimmed.isBlank()) return trimmed
    val normalized = trimmed.replace('-', '/')
    return normalized
        .split('/')
        .lastOrNull()
        ?.takeIf { it.all(Char::isDigit) }
        ?.toIntOrNull()
        ?.toString()
        ?: trimmed
}

private fun String.isCalendarDayNumber(): Boolean =
    toIntOrNull()?.let { it in 1..31 } == true

private fun String?.toYearMonthOrNull(): Pair<Int, Int>? {
    val normalized = this?.trim().orEmpty().replace('-', '/')
    val parts = normalized.split('/')
    if (parts.size < 2) return null
    val year = parts.getOrNull(0)?.toIntOrNull() ?: return null
    val month = parts.getOrNull(1)?.toIntOrNull() ?: return null
    if (month !in 1..12) return null
    return year to month
}

private fun firstDayColumnOfMonth(year: Int, month: Int): Int {
    val calendar = java.util.Calendar.getInstance(java.util.Locale.TAIWAN).apply {
        set(java.util.Calendar.YEAR, year)
        set(java.util.Calendar.MONTH, month - 1)
        set(java.util.Calendar.DAY_OF_MONTH, 1)
    }
    return calendar.get(java.util.Calendar.DAY_OF_WEEK) - java.util.Calendar.SUNDAY
}

private fun dayOfWeekOfDate(year: Int, month: Int, day: Int): Int {
    val calendar = java.util.Calendar.getInstance(java.util.Locale.TAIWAN).apply {
        set(java.util.Calendar.YEAR, year)
        set(java.util.Calendar.MONTH, month - 1)
        set(java.util.Calendar.DAY_OF_MONTH, day)
    }
    return calendar.get(java.util.Calendar.DAY_OF_WEEK)
}

private fun String.normalizedLabel(): String =
    filterNot { it.isWhitespace() }

private fun String.toReservationSectionOrNull(): ReservationSection? {
    val value = trim()
    return when {
        value.contains("初診預約") -> ReservationSection.INITIAL
        value.contains("複診掛號") || value.contains("復診掛號") -> ReservationSection.RETURN_VISIT
        else -> null
    }
}

private fun String?.toVisitSessionOrNull(): String? {
    val value = this?.trim().orEmpty()
    return when {
        value.contains("上午") -> "上午診"
        value.contains("下午") -> "下午診"
        value.contains("晚上") || value.contains("夜間") || value.contains("夜診") -> "夜間診"
        else -> null
    }
}
