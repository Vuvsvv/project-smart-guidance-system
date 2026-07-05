package com.example.medicalaiguidance.screen

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.medicalaiguidance.navigation.Route
import com.example.medicalaiguidance.service.MyAccessibilityService
import com.example.medicalaiguidance.viewmodel.ConfirmViewModel

@Composable
fun ConfirmNeedScreen(
    navController: NavController,
    viewModel: ConfirmViewModel = viewModel()
) {
    val context = LocalContext.current
    val appointment by viewModel.appointmentInfo.collectAsState()

    // 💡 控制提醒彈窗的顯示
    var showPermissionDialog by remember { mutableStateOf(false) }
    // 新增：控制再次確認彈窗
    var showConfirmDialog by remember { mutableStateOf(false) }
    val primaryDark = Color(0xFF2C4E4E)
    val bgGradient = Brush.verticalGradient(colors = listOf(Color(0xFFF5F9F9), Color(0xFFEBF2F2)))
    val cardHeaderGradient = Brush.verticalGradient(colors = listOf(Color(0xFF6E9999), Color(0xFF385E5E)))

    // 💡 權限檢查邏輯
    fun isServiceEnabled(): Boolean {
        val expectedService = "${context.packageName}/${MyAccessibilityService::class.java.name}"
        val enabled = try {
            Settings.Secure.getInt(context.contentResolver, Settings.Secure.ACCESSIBILITY_ENABLED)
        } catch (e: Exception) { 0 }

        if (enabled == 1) {
            val enabledServices = Settings.Secure.getString(context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
            return enabledServices?.contains(expectedService) == true
        }
        return false
    }

    if (appointment == null) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator(color = primaryDark)
        }
        return
    }

    val currentApt = appointment!!
    val targetDept = currentApt.department.name
    val targetClinic = currentApt.department.clinicName
    val targetDoctor = currentApt.doctor.name
    val targetTime = currentApt.timeSlot
    val targetDayString = "${currentApt.date} ${currentApt.dayOfWeek}"

    // 🚀 提醒小視窗 (AlertDialog)
    if (showPermissionDialog) {
        AlertDialog(
            onDismissRequest = { showPermissionDialog = false },
            confirmButton = {
                Button(
                    onClick = {
                        showPermissionDialog = false
                        context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF036A6D))
                ) { Text("前往設定") }
            },

            title = { Text("開啟紅框引導功能", fontWeight = FontWeight.Bold) },
            text = {
                Text("為了讓系統能在台北榮總app顯示「紅框引導」，請至手機「設定」>「協助工具」中開啟「Medical AI Guidance」。")
            },
            shape = RoundedCornerShape(28.dp),
            containerColor = Color.White
        )
    }

    // ✅ 再次確認視窗 (精修版)
    if (showConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showConfirmDialog = false },
            shape = RoundedCornerShape(24.dp),
            containerColor = Color.White,
            // 💡 使用方便自訂內容的引數，把所有 UI 元素綁在一個 Column 裡
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    // 1. 標題：置中、加粗、放大
                    Text(
                        text = "再次確認",
                        fontSize = 24.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF1A2E2E)
                    )

                    Spacer(modifier = Modifier.height(16.dp)) //標題與內文的間距

                    // 2. 副標題/內文：置中、字體適中
                    Text(
                        text = "即將前往台北榮總app",
                        fontSize = 18.sp,
                        color = Color(0xFF1A2E2E),
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(16.dp)) //內文與底部按鈕的間距

                    // 3. 按鈕列：橫向並排、平分寬度
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        //  取消按鈕 (左側)
                        Button(
                            onClick = { showConfirmDialog = false },
                            modifier = Modifier
                                .weight(1f)
                                .height(56.dp)
                                .shadow(2.dp, RoundedCornerShape(16.dp)),
                            shape = RoundedCornerShape(16.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Color(0xFFF0F4F5) // 淡灰色/淡青色背景
                            )
                        ) {
                            Text(
                                text = "取消",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF385E5E) // 深青色文字
                            )
                        }

                        //  確認按鈕 (右側)
                        Button(
                            onClick = {
                                showConfirmDialog = false
                                MyAccessibilityService.updateTarget(
                                    department = targetDept,
                                    clinic = targetClinic,
                                    doctor = targetDoctor,
                                    date = currentApt.date
                                )
                                val packageName = "tw.com.bicom.VGHTPE"
                                val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
                                if (launchIntent != null) {
                                    context.startActivity(launchIntent)
                                } else {
                                    val webIntent = Intent(Intent.ACTION_VIEW, Uri.parse("https://www.vghtpe.gov.tw/Index.action"))
                                    context.startActivity(webIntent)
                                }
                            },
                            modifier = Modifier
                                .weight(1f)
                                .height(56.dp)
                                .shadow(4.dp, RoundedCornerShape(16.dp)),
                            shape = RoundedCornerShape(16.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Color(0xFF385E5E) // 配合你原本定義的深青色
                            )
                        ) {
                            Text(
                                text = "確認",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    }
                }
            },
            // 💡 把按鈕都寫在 text 的 Column 裡了，原本的 confirm/dismiss Button 就放 null
            confirmButton = {},
            dismissButton = {}
        )
    }

    Column(
        modifier = Modifier.fillMaxSize().background(brush = bgGradient).statusBarsPadding()
    ) {
        // 1. 頂部導航列
        Box(modifier = Modifier.fillMaxWidth().height(80.dp).padding(horizontal = 20.dp), contentAlignment = Alignment.Center) {
            Box(
                modifier = Modifier.align(Alignment.CenterStart).size(48.dp).shadow(6.dp, RoundedCornerShape(16.dp))
                    .background(Color.White, RoundedCornerShape(16.dp)).clickable { navController.popBackStack() },
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Default.ArrowBack, "返回", tint = primaryDark, modifier = Modifier.size(22.dp))
            }
            Text(text = "準備好了嗎", fontSize = 24.sp, fontWeight = FontWeight.Bold, color = primaryDark)
        }

        // 2. 核心大卡片區塊
        Card(
            modifier = Modifier.fillMaxWidth().weight(1f).padding(horizontal = 24.dp, vertical = 8.dp).shadow(12.dp, RoundedCornerShape(40.dp)),
            shape = RoundedCornerShape(40.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White)
        ) {
            Column(modifier = Modifier.fillMaxSize()) {
                Box(modifier = Modifier.fillMaxWidth().height(140.dp).background(brush = cardHeaderGradient), contentAlignment = Alignment.Center) {
                    Box(modifier = Modifier.size(80.dp).background(Color.White.copy(alpha = 0.15f), CircleShape), contentAlignment = Alignment.Center) {
                        Icon(Icons.Default.MedicalServices, null, tint = Color.White, modifier = Modifier.size(42.dp))
                    }
                }

                Column(
                    modifier = Modifier.fillMaxWidth().weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 28.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    InfoRowItem(Icons.Default.LocalHospital, "科別", "$targetDept $targetClinic")
                    HorizontalDivider(color = Color(0xFFEBF2F2), thickness = 1.dp)
                    InfoRowItem(Icons.Default.Accessibility, "看診醫師", "$targetDoctor 醫師")
                    HorizontalDivider(color = Color(0xFFEBF2F2), thickness = 1.dp)
                    InfoRowItem(Icons.Default.AccessTime, "預約時間", "$targetDayString $targetTime")
                }
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        // 3. 底部按鈕列
        Column(
            modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(start = 24.dp, end = 24.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // 前往掛號
            Box(
                modifier = Modifier.fillMaxWidth().height(60.dp).shadow(6.dp, RoundedCornerShape(30.dp))
                    .background(brush = cardHeaderGradient, RoundedCornerShape(30.dp))
                    .clickable {

                        if (isServiceEnabled()) {
                            // ✅ 權限已開啟 → 彈出再次確認視窗（不直接跳轉）
                            showConfirmDialog = true
                        } else {
                            // 權限未開啟 → 彈出權限提示視窗
                            showPermissionDialog = true
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.AutoMirrored.Filled.ExitToApp, null, tint = Color.White, modifier = Modifier.size(24.dp))
                    Spacer(modifier = Modifier.width(10.dp))
                    Text("前往掛號", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                }
            }

            // 重新詢問
            Box(
                modifier = Modifier.fillMaxWidth().height(60.dp).shadow(2.dp, RoundedCornerShape(30.dp))
                    .background(Color(0xFFF0F4F4), RoundedCornerShape(30.dp))
                    .clickable {
                        navController.navigate(Route.CHAT) { popUpTo(Route.HOME) }
                    },
                contentAlignment = Alignment.Center
            ) {
                Text("重新詢問", color = primaryDark, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
fun InfoRowItem(icon: ImageVector, label: String, title: String, subLabel: String? = null) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(modifier = Modifier.weight(1f)) {
            Text(label, fontSize = 14.sp, color = Color(0xFF7A8B8B), fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(4.dp))
            Text(title, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF1A2E2E))
            subLabel?.let { Text(it, fontSize = 15.sp, color = Color(0xFF4A5959)) }
        }
        Spacer(Modifier.width(12.dp))
        Icon(icon, null, tint = Color(0xFF2C4E4E), modifier = Modifier.size(38.dp))
    }
}
