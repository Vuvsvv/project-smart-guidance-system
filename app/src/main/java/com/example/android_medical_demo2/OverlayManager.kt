package com.example.android_medical_demo2

import android.content.Context
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.view.WindowManager
import android.provider.Settings
class OverlayManager(private val context: Context) {
    private val windowManager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private var view: View? = null
    private var isAdded = false

    fun show(rect: android.graphics.Rect) {

        if (!Settings.canDrawOverlays(context)) {
            return
        }

        // 🔥 1. 抓出「狀態列」的高度 (時間、電量那一條)
        var statusBarHeight = 0
        val resourceId = context.resources.getIdentifier("status_bar_height", "dimen", "android")
        if (resourceId > 0) {
            statusBarHeight = context.resources.getDimensionPixelSize(resourceId)
        }

        // 加上一點 Padding (留白)，讓框框不會緊貼著字
        val padding = 15
        val targetWidth = rect.width() + (padding * 2)
        val targetHeight = rect.height() + (padding * 2)

        if (view == null) {
            view = View(context)
            val shape = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 20f // 圓角設定
                setStroke(12, 0xFFFF0000.toInt())
                setColor(0x4DFF0000)
            }
            view!!.background = shape
        }

        val params = WindowManager.LayoutParams(
            targetWidth, targetHeight,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = android.view.Gravity.TOP or android.view.Gravity.START

            // 🔥 2. 核心解藥：X 座標照舊，Y 座標必須扣掉狀態列的高度！
            x = rect.left - padding
            y = rect.top - padding - statusBarHeight
        }

        if (!isAdded) {
            windowManager.addView(view, params)
            isAdded = true
        } else {
            windowManager.updateViewLayout(view, params)
        }
    }

    // 🔥 新增：讓發瘋殘影消失的魔法
    fun hide() {
        if (isAdded && view != null) {
            windowManager.removeView(view)
            isAdded = false
        }
    }
}