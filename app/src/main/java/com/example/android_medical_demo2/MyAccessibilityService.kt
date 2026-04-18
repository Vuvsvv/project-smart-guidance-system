package com.example.android_medical_demo2

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray  // 🔥 新增：處理 JSON 陣列
import org.json.JSONObject
import android.widget.Toast

class MyAccessibilityService : AccessibilityService() {
    // 🔥 把這整塊確實貼到類別裡面！
    companion object {
        private var pendingDoctor: String? = null
        private var pendingTime: String? = null
        private var pendingClinic: String? = null
        private var isFirstVisit: Boolean = true
        private var shouldUpdateScript = false
        private var forceReset = false // 🧹 新增：強制重置開關

        fun updateTarget(doctor: String, time: String, clinic: String, firstVisit: Boolean) {
            pendingDoctor = doctor
            pendingTime = time
            pendingClinic = clinic
            isFirstVisit = firstVisit
            shouldUpdateScript = true
        }

        // 🧹 新增：讓外部呼叫，把一切歸零的方法
        fun resetTarget() {
            forceReset = true
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

    override fun onServiceConnected() {
        super.onServiceConnected()
        overlay = OverlayManager(this)

        // 模擬 AI 傳來的結果
        val targetClinic = "一般骨科"
        val targetDoctor = "邱方遙"
        val targetTime = "23" // 👈 補上這個時間參數！(對應妳題目流程裡的 "23")
        val isFirstVisit = true

        // 動態生成腳本
        generateDynamicScript(targetClinic, targetDoctor, targetTime, isFirstVisit)
    }

    // 🔥 注意看括號裡面！把 time: String 加進去！
    private fun generateDynamicScript(clinic: String, doctor: String, time: String, isFirstVisit: Boolean) {
        val fileName = if (isFirstVisit) "Initial_diagnosis.json" else "Followup_visit.json"

        // 🧠 魔法 1：找大科別
        val department = findDepartmentInJson(fileName, clinic)
        // 🧠 魔法 2：找醫生的精確代碼/名字
        val exactDoctor = findDoctorInJson(doctor)

        if (department != null && exactDoctor != null) {
            script = listOf(
                "行動掛號",
                "繼續掛號",
                "依門診科別",
                department, // 例如 "外科系"
                clinic,     // 例如 "一般骨科"
                "選擇看診時間",
                time,       // 🔥 這裡才有 time 可以用！
                exactDoctor,
                "填寫個人資料",
                "請輸入身分證號",
                "請輸入病患姓名",
                "民國${rocYear}年",
                "${month}月",
                "${day}日",
                "確認送出"
            )
            Log.d("AjaxDebug", "🎉 腳本生成成功！大類別：$department, 醫生：$exactDoctor")
        } else {
            Log.e("AjaxDebug", "💀 慘了！科別 $department 或是 醫生 $exactDoctor 找不到對應資料！")
        }
    }

    // 查科別的邏輯 (維持不變)
    private fun findDepartmentInJson(fileName: String, targetClinic: String): String? {
        try {
            val inputStream = assets.open(fileName)
            val jsonString = inputStream.bufferedReader().use { it.readText() }
            val jsonObject = JSONObject(jsonString)

            val keys = jsonObject.keys()
            while (keys.hasNext()) {
                val departmentName = keys.next()
                val clinicsArray = jsonObject.getJSONArray(departmentName)
                for (i in 0 until clinicsArray.length()) {
                    if (clinicsArray.getString(i) == targetClinic) {
                        return departmentName
                    }
                }
            }
        } catch (e: Exception) {
            Log.e("AjaxDebug", "讀取 $fileName 失敗：${e.message}")
        }
        return null
    }

    // 🔥 新增：查醫生的邏輯
    private fun findDoctorInJson(targetDoctor: String): String? {
        try {
            val inputStream = assets.open("doctor.json")
            val jsonString = inputStream.bufferedReader().use { it.readText() }
            // 注意！doctor.json 最外層是 Array ([...])，不是 Object ({...})
            val jsonArray = JSONArray(jsonString)

            for (i in 0 until jsonArray.length()) {
                val doctorObj = jsonArray.getJSONObject(i)
                val nameField = doctorObj.getString("name")
                val codeField = doctorObj.getString("code")

                // 如果 AI 給的名字剛好等於 code，或者被包含在 name 裡面 (如 "骨科部_邱方遙")
                if (codeField == targetDoctor || nameField.contains(targetDoctor)) {
                    return codeField // 回傳精確的 code 讓畫面去點擊
                }
            }
        } catch (e: Exception) {
            Log.e("AjaxDebug", "讀取 doctor.json 失敗：${e.message}")
        }
        return null
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return

        // 🧹 1. 如果收到重置指令，清空一切！
        if (forceReset) {
            script = emptyList() // 清空腳本
            currentStepIndex = 0 // 步驟歸零
            overlay?.hide()      // 把畫面上的紅框框消掉
            forceReset = false
            Log.d("AjaxDebug", "🧹 收到重置指令，腳本已清空，從頭開始！")
        }

// 🔄 2. 如果收到新任務，重新製造腳本！
        if (shouldUpdateScript) {
            val doctor = pendingDoctor ?: ""
            val clinic = pendingClinic ?: ""
            val time = pendingTime ?: "" // 🔥 把時間也抓出來！

            // 🔥 注意看這裡！呼叫的時候，要把 time 放在第三個位置傳進去！
            generateDynamicScript(clinic, doctor, time, isFirstVisit)

            currentStepIndex = 0
            shouldUpdateScript = false
            Log.d("AjaxDebug", "🔄 收到新任務，腳本生成完畢！目標科別：$clinic")
        }

        // 🛑 3. 阿賈克斯防護罩：確認現在畫面在哪個 APP 裡
        // 如果是妳自己的 APP (com.example.android_medical_demo2)，就直接 return 裝死，不要亂找按鈕！
        val packageName = event.packageName?.toString() ?: rootInActiveWindow?.packageName?.toString() ?: ""
        if (packageName.contains("android_medical_demo2")) {
            return
        }

        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            val className = event.className?.toString() ?: ""
            isDialogOpen = className.contains("Dialog") || className.contains("PopupWindow") || className.contains("Menu")
        }

        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||
            event.eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) {
            val root = rootInActiveWindow ?: return

            // 只有腳本不是空的，才去執行尋找框框的動作
            if (script.isNotEmpty()) {
                handleStep(root)
            }
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

        // 避免在日期選單彈出時亂指
        if (isDateStep && (isDialogOpen || yearCount > 3 || monthCount > 3 || dayCount > 3)) {
            overlay?.hide()
            return
        }

        val isWaitStep = currentKeyword.contains("請輸入") || isDateStep

        // 單步推進邏輯
        if (!isWaitStep && currentStepIndex + 1 < script.size) {
            val nextKeyword = script[currentStepIndex + 1]
            val nextNode = allNodes.find { it.text.contains(nextKeyword) }
            if (nextNode != null) {
                currentStepIndex++
                Log.d("AjaxDebug", "🎉 發現下一步！強制推進到第 ${currentStepIndex + 1} 步: $nextKeyword")
            }
        }

        val finalKeyword = script[currentStepIndex]
        val currentTarget = allNodes.find { it.text.contains(finalKeyword) }

        if (currentTarget != null) {
            // 🎯 正常情況：找到目標，畫框框！
            highlight(currentTarget.rect, "步驟 ${currentStepIndex + 1}: 請操作 $finalKeyword")
        } else {
            // 🚀 千里眼特製機制：往下找 1~2 步 (應付手風琴選單展開，或畫面往下捲動導致字被擠掉)
            var foundFuture = false
            for (i in 1..2) {
                if (currentStepIndex + i < script.size) {
                    val futureKeyword = script[currentStepIndex + i]
                    val futureNode = allNodes.find { it.text.contains(futureKeyword) }
                    if (futureNode != null) {
                        currentStepIndex += i
                        highlight(futureNode.rect, "🚀 畫面跳躍！直接進入步驟 ${currentStepIndex + 1}: 請操作 $futureKeyword")
                        foundFuture = true
                        break
                    }
                }
            }
            if (foundFuture) return

            // 🕰️ 時光倒流機制：檢查是不是退回上一步了
            if (currentStepIndex > 0) {
                val prevKeyword = script[currentStepIndex - 1]
                val prevNode = allNodes.find { it.text.contains(prevKeyword) }
                if (prevNode != null) {
                    currentStepIndex-- // 💡 腳本狀態跟著退回上一步
                    highlight(prevNode.rect, "退回步驟 ${currentStepIndex + 1}: 請操作 $prevKeyword")
                    return
                }
            }

            // 💀 真的都找不到，代表她點進錯誤的頁面了 (阿嬤迷路了)
            if (!isDialogOpen) {
                Log.w("AjaxDebug", "💀 找不到目標 $finalKeyword！阿嬤可能按錯了！")

                // 隱藏框框，避免亂指
                overlay?.hide()

                // 彈出提示教阿嬤怎麼自救
                Toast.makeText(applicationContext, "哎呀！好像按錯了，請按一下手機的「返回鍵」退回上一頁喔！", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun findAllTextNodes(root: AccessibilityNodeInfo): List<NodeData> {
        val result = mutableListOf<NodeData>()
        traverse(root, result)
        return result
    }

    private fun traverse(node: AccessibilityNodeInfo?, list: MutableList<NodeData>) {
        if (node == null) return
        val rawText = node.text?.toString() ?: ""
        val rawDesc = node.contentDescription?.toString() ?: ""
        val rawHint = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            node.hintText?.toString() ?: ""
        } else {
            ""
        }

        val isFilled = rawText.isNotEmpty() && !rawText.contains("請輸入") && rawText != rawHint && rawText != rawDesc
        val combinedText = if (isFilled) rawText else "$rawText $rawDesc $rawHint".trim()

        if (combinedText.isNotEmpty()) {
            val rect = android.graphics.Rect()
            node.getBoundsInScreen(rect)
            if (rect.width() > 0 && rect.height() > 0) {
                list.add(NodeData(combinedText, rect))
            }
        }

        for (i in 0 until node.childCount) {
            traverse(node.getChild(i), list)
        }
    }

    private fun highlight(rect: Rect, msg: String) {
        val targetRect = if (rect.height() > 800) {
            Rect(rect.centerX() - 150, rect.centerY() - 50, rect.centerX() + 150, rect.centerY() + 50)
        } else {
            rect
        }
        overlay?.show(targetRect)
        Log.d("AjaxDebug", msg)
    }
}

data class NodeData(val text: String, val rect: Rect)