package com.example.android_medical_demo2

import android.content.Context
import android.util.Log
import org.json.JSONObject

class ScheduleManager(private val context: Context) {

    // 定義一個資料格式，用來包裝我們要回傳給前端 (對話框) 的結果
    data class MatchResult(
        val isSuccess: Boolean,
        val doctor: String,
        val time: String,
        val message: String
    )

    // 🔥 核心演算法：找出最適合的門診時段
    fun findBestSlot(targetClinic: String, preferredDoctor: String?, preferredTime: String?): MatchResult {
        try {
            // 1. 讀取我們剛剛建的假班表
            val inputStream = context.assets.open("mock_schedule.json")
            val jsonString = inputStream.bufferedReader().use { it.readText() }
            val rootObj = JSONObject(jsonString)

            // 2. 防呆：如果連這個科別都沒有
            if (!rootObj.has(targetClinic)) {
                return MatchResult(false, "", "", "找不到「$targetClinic」的班表耶，要不要確認一下科別？")
            }

            val clinicObj = rootObj.getJSONObject(targetClinic)

            // 3. 情境 A：使用者有指定醫生
            if (preferredDoctor != null && clinicObj.has(preferredDoctor)) {
                val timesArray = clinicObj.getJSONArray(preferredDoctor)
                val availableTimes = mutableListOf<String>()
                for (i in 0 until timesArray.length()) {
                    availableTimes.add(timesArray.getString(i))
                }

                // 3-1. 使用者連時間都指定了
                if (preferredTime != null) {
                    if (availableTimes.contains(preferredTime)) {
                        return MatchResult(true, preferredDoctor, preferredTime, "太棒了！$preferredDoctor 醫師在 $preferredTime 有診！")
                    } else {
                        return MatchResult(false, preferredDoctor, "", "$preferredDoctor 醫師在 $preferredTime 沒診喔。他有空的時間是：${availableTimes.joinToString(", ")}，請問要改時間嗎？")
                    }
                }
                // 3-2. 使用者只指定醫生，沒指定時間 -> 給他最快的一班
                else {
                    val firstTime = availableTimes.firstOrNull() ?: ""
                    return MatchResult(true, preferredDoctor, firstTime, "幫您安排 $preferredDoctor 醫師最快的診：$firstTime，可以嗎？")
                }
            }

            // 4. 情境 B：沒指定醫生，或是指定的醫生查不到 -> 直接隨機塞一個該科別有空的醫生
            val doctors = clinicObj.keys()
            if (doctors.hasNext()) {
                val firstDoctor = doctors.next()
                val timesArray = clinicObj.getJSONArray(firstDoctor)
                val firstTime = timesArray.getString(0)
                return MatchResult(true, firstDoctor, firstTime, "沒特別指定醫生對吧？幫您安排最快的：$firstDoctor 醫師 ($firstTime)，請問確認掛號嗎？")
            }

        } catch (e: Exception) {
            Log.e("AjaxDebug", "解析假班表失敗啦：${e.message}")
        }

        return MatchResult(false, "", "", "系統出了一點小狀況，請稍後再試！")
    }
}