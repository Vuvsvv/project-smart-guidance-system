package com.example.android_medical_demo2

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.example.android_medical_demo2.MyAccessibilityService // 確保有引用到妳的 Service

class MainActivity : AppCompatActivity() {

    private lateinit var scheduleManager: ScheduleManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)

        scheduleManager = ScheduleManager(this)

        // 1. 檢查並請求權限 (這兩關沒過，妳的紅框框跟自動化就不會動)
        checkPermissions()

        // 2. 找畫面上的按鈕 (假設妳 XML 裡有一個 id 為 btn_start_demo 的按鈕)
        val startBtn = findViewById<Button>(R.id.btn_start_demo)

        startBtn.setOnClickListener {
            // 🔥 新增這行：按下按鈕的第一件事，就是叫服務把所有舊資料跟紅框框都清掉！
            MyAccessibilityService.resetTarget()

            // 🌟 模擬情境：使用者說「我想掛一般骨科，我想看邱方遙」
            simulateAiRequest("一般骨科", "邱方遙", "星期三下午")
        }
    }

    private fun simulateAiRequest(clinic: String, doctor: String?, time: String?) {
        // 呼叫我們寫的大腦邏輯
        val result = scheduleManager.findBestSlot(clinic, doctor, time)

        if (result.isSuccess) {
            // 🧠 彈出確認視窗，這就是妳說的「告知使用者，不滿意再改」
            showConfirmationDialog(result)
        } else {
            // 🧠 處理衝突 (例如醫生沒診)，這裡可以直接用 Toast 或是另一個對話框告知
            Toast.makeText(this, result.message, Toast.LENGTH_LONG).show()
        }
    }

    private fun showConfirmationDialog(result: ScheduleManager.MatchResult) {
        AlertDialog.Builder(this)
            .setTitle("掛號確認")
            .setMessage(result.message + "\n\n確定要開始自動掛號嗎？")
            .setPositiveButton("確定") { _, _ ->
                // 🔥 核心動作：把最終決定好的劇本，傳給無障礙服務！
                MyAccessibilityService.updateTarget(
                    result.doctor,
                    result.time,
                    "一般骨科", // 這裡可以根據邏輯動態傳
                    true // 假設為初診
                )

                // 🚀 修正：不要再去那個死透的網址了！改開榮總官方 APP
                val hospitalAppPackage = "tw.com.bicom.VGHTPE" // 台北榮總官方 APP 的包名
                val launchIntent = packageManager.getLaunchIntentForPackage(hospitalAppPackage)

                if (launchIntent != null) {
                    // 偵測到手機有安裝官方 APP，直接帥氣開啟！
                    startActivity(launchIntent)
                } else {
                    // 如果沒安裝官方 APP，就去新的、正確的掛號網頁版
                    val webIntent = Intent(Intent.ACTION_VIEW, Uri.parse("https://www6.vghtpe.gov.tw/opd/m/"))
                    startActivity(webIntent)
                    Toast.makeText(this@MainActivity, "建議去 Google Play 下載「台北榮總行動就醫服務」APP，自動點擊才會順利喔！", Toast.LENGTH_LONG).show()
                }
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun checkPermissions() {
        if (!Settings.canDrawOverlays(this)) {
            val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
            startActivity(intent)
        }

        AlertDialog.Builder(this)
            .setTitle("需要開啟輔助工具")
            .setMessage("等一下跳轉到設定後：\n\n1. 點擊『已安裝的應用程式』\n2. 找到『Android_Medical_Demo2』並開啟\n3. 🔥 開啟後，請務必按手機的「返回鍵」回到這裡喔！") // <- 加上這句提醒
            .setPositiveButton("好，我知道了") { _, _ ->
                val accessibilityIntent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                startActivity(accessibilityIntent)
            }
            .setCancelable(false)
            .show()
    }
}