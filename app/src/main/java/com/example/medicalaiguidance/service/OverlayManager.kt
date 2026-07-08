package com.example.medicalaiguidance.service

import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.TextView

class OverlayManager(private val context: Context) {
    private val windowManager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private var overlayRoot: FrameLayout? = null
    private var borderView: View? = null
    private var bubbleView: TextView? = null
    private var isAdded = false

    fun show(rect: Rect, message: String? = null) {
        if (!Settings.canDrawOverlays(context)) return

        val statusBarHeight = context.statusBarHeight()
        val padding = 15
        val bubbleHeight = if (message.isNullOrBlank()) 0 else 56
        val bubbleGap = if (message.isNullOrBlank()) 0 else 8
        val minBubbleWidth = if (message.isNullOrBlank()) 0 else 520
        val borderWidth = rect.width() + padding * 2
        val borderHeight = rect.height() + padding * 2
        val targetWidth = maxOf(borderWidth, minBubbleWidth)
        val targetHeight = bubbleHeight + bubbleGap + borderHeight
        val borderLeft = (targetWidth - borderWidth) / 2
        val borderTop = bubbleHeight + bubbleGap

        ensureViews()
        updateBorder(borderLeft, borderTop, borderWidth, borderHeight)
        updateBubble(message, targetWidth, bubbleHeight)

        Log.d(
            "vgh_id_detect",
            "顯示紅框 rect=${rect.toShortString()} size=${targetWidth}x$targetHeight message=${message.orEmpty()}"
        )

        val params = WindowManager.LayoutParams(
            targetWidth,
            targetHeight,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = rect.left - padding - borderLeft
            y = rect.top - padding - statusBarHeight - borderTop
        }

        if (!isAdded) {
            windowManager.addView(overlayRoot, params)
            isAdded = true
        } else {
            windowManager.updateViewLayout(overlayRoot, params)
        }
    }

    fun showMessage(message: String) {
        if (!Settings.canDrawOverlays(context)) return

        val screenWidth = context.resources.displayMetrics.widthPixels
        val statusBarHeight = context.statusBarHeight()
        val bubbleWidth = (screenWidth * 0.86f).toInt()
        val bubbleHeight = 72

        ensureViews()
        borderView?.visibility = View.GONE
        updateBubble(message, bubbleWidth, bubbleHeight)

        Log.d("vgh_id_detect", "顯示提示泡泡 message=$message")

        val params = WindowManager.LayoutParams(
            bubbleWidth,
            bubbleHeight,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (screenWidth - bubbleWidth) / 2
            y = 130 - statusBarHeight
        }

        if (!isAdded) {
            windowManager.addView(overlayRoot, params)
            isAdded = true
        } else {
            windowManager.updateViewLayout(overlayRoot, params)
        }
    }

    fun hide() {
        if (isAdded && overlayRoot != null) {
            windowManager.removeView(overlayRoot)
            isAdded = false
        }
    }

    private fun ensureViews() {
        if (overlayRoot != null) return

        overlayRoot = FrameLayout(context)

        borderView = View(context).apply {
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 20f
                setStroke(12, 0xFFFF0000.toInt())
                setColor(0x4DFF0000)
            }
        }

        bubbleView = TextView(context).apply {
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadius = 18f
                setColor(0xEE263238.toInt())
            }
            setTextColor(Color.WHITE)
            textSize = 16f
            gravity = Gravity.CENTER
            setPadding(18, 0, 18, 0)
        }

        overlayRoot?.addView(borderView)
        overlayRoot?.addView(bubbleView)
    }

    private fun updateBorder(left: Int, top: Int, width: Int, height: Int) {
        borderView?.visibility = View.VISIBLE
        borderView?.layoutParams = FrameLayout.LayoutParams(width, height).apply {
            leftMargin = left
            topMargin = top
        }
    }

    private fun updateBubble(message: String?, width: Int, height: Int) {
        if (message.isNullOrBlank()) {
            bubbleView?.visibility = View.GONE
            return
        }

        bubbleView?.visibility = View.VISIBLE
        bubbleView?.text = message
        bubbleView?.layoutParams = FrameLayout.LayoutParams(width, height)
    }
}

private fun Context.statusBarHeight(): Int {
    val resourceId = resources.getIdentifier("status_bar_height", "dimen", "android")
    return if (resourceId > 0) resources.getDimensionPixelSize(resourceId) else 0
}
