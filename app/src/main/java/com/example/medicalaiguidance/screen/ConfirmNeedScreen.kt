package com.example.medicalaiguidance.screen

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.medicalaiguidance.R
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

    // 控制提醒彈窗的顯示
    var showPermissionDialog by remember { mutableStateOf(false) }
    // 控制再次確認彈窗
    var showConfirmDialog by remember { mutableStateOf(false) }

    val primaryDark = Color(0xFF376F72)
    val badgeBg = Color(0xFFD9EAE7)
    val bgGradient = Brush.verticalGradient(colors = listOf(Color(0xFFF2FAF8), Color(0xFFF2FAF8)))

    val fontScale = LocalDensity.current.fontScale
    val cardMinHeight = when {
        fontScale >= 1.3f -> 500.dp
        fontScale >= 1.15f -> 460.dp
        else -> 420.dp
    }
    val cardMaxHeight = when {
        fontScale >= 1.3f -> 620.dp
        fontScale >= 1.15f -> 560.dp
        else -> 500.dp
    }
    val infoContentMaxHeight = when {
        fontScale >= 1.3f -> 430.dp
        fontScale >= 1.15f -> 380.dp
        else -> 320.dp
    }

    // 權限檢查邏輯
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

    // 提醒小視窗 (AlertDialog)
    if (showPermissionDialog) {
        AlertDialog(
            onDismissRequest = { showPermissionDialog = false },
            shape = RoundedCornerShape(24.dp),
            containerColor = Color.White,
            title = {
                Text(
                    text = "開啟紅框引導功能",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )
            },
            text = {
                Text(
                    text = "為了讓系統能在台北榮總 app 顯示「紅框引導」，請至手機「設定」>「協助工具」中開啟「Medical AI Guidance」。",
                    fontSize = 15.sp,
                    lineHeight = 22.sp,
                )
            },
            confirmButton = {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp)
                            .background(Color(0xFFD5E5E5).copy(alpha = 0.35f), RoundedCornerShape(24.dp))
                            .clip(RoundedCornerShape(24.dp))
                            .clickable { showPermissionDialog = false },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "取消", color = primaryDark, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp)
                            .background(color = primaryDark, RoundedCornerShape(24.dp))
                            .clip(RoundedCornerShape(24.dp))
                            .clickable {
                                showPermissionDialog = false
                                context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Settings, null, tint = Color.White, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(text = "前往設定", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            },
            dismissButton = null
        )
    }

    // 再次確認視窗
    if (showConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showConfirmDialog = false },
            shape = RoundedCornerShape(24.dp),
            containerColor = Color.White,
            title = {
                Text(
                    text = "再次確認",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )
            },
            text = {
                Text(
                    text = "即將前往台北榮總 app",
                    fontSize = 15.sp,
                    lineHeight = 22.sp,
                )
            },
            confirmButton = {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp)
                            .background(Color(0xFFD5E5E5).copy(alpha = 0.35f), RoundedCornerShape(24.dp))
                            .clip(RoundedCornerShape(24.dp))
                            .clickable { showConfirmDialog = false },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "取消", color = primaryDark, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp)
                            .background(color = primaryDark, RoundedCornerShape(24.dp))
                            .clip(RoundedCornerShape(24.dp))
                            .clickable {
                                showConfirmDialog = false
                                MyAccessibilityService.updateTarget(
                                    department = targetDept,
                                    clinic = targetClinic,
                                    doctor = targetDoctor,
                                    date = currentApt.date,
                                    timeSlot = targetTime
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
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "確認", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    }
                }
            },
            dismissButton = null
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
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f, fill = false)
                .padding(horizontal = 24.dp, vertical = 8.dp)
        ) {
            // 調整：羊咩咩吉祥物
            Image(
                painter = painterResource(id = R.drawable.sheep_2),
                contentDescription = null,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .offset(x = (12).dp, y = (-60).dp)
                    .size(120.dp)
            )

            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 28.dp) // 調整：從 56.dp 改為 44.dp，使卡片整體往上移動
                    .heightIn(min = cardMinHeight, max = cardMaxHeight)
                    .shadow(2.dp, RoundedCornerShape(30.dp))
                    .border(width = 10.dp, color = badgeBg.copy(alpha = 0.8f), shape = RoundedCornerShape(30.dp)),
                shape = RoundedCornerShape(30.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White)
            ) {
                Column(modifier = Modifier.fillMaxWidth()) {

                    Box(
                        modifier = Modifier
                            .align(Alignment.CenterHorizontally)
                            .padding(start = 28.dp, top = 36.dp, end = 28.dp)
                            .background(badgeBg, RoundedCornerShape(20.dp))
                            .padding(horizontal = 16.dp, vertical = 8.dp)
                    ) {
                        Text(
                            text = "掛號資訊確認",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = primaryDark
                        )
                    }

                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = infoContentMaxHeight)
                            .verticalScroll(rememberScrollState())
                            .padding(start = 28.dp, end = 28.dp, top = 24.dp, bottom = 40.dp),
                        verticalArrangement = Arrangement.spacedBy(20.dp)
                    ) {
                        InfoRowItem(
                            icon = Icons.Default.LocalHospital,
                            iconPainter = painterResource(id = R.drawable.ic_hospital),
                            label = "科別",
                            title = "$targetDept $targetClinic"
                        )
                        HorizontalDivider(color = Color(0xFFEBF2F2), thickness = 1.dp)
                        InfoRowItem(
                            icon = Icons.Default.Person,
                            iconPainter = painterResource(id = R.drawable.ic_doctor),
                            label = "看診醫師",
                            title = "$targetDoctor 醫師"
                        )
                        HorizontalDivider(color = Color(0xFFEBF2F2), thickness = 1.dp)
                        InfoRowItem(
                            icon = Icons.Default.AccessTime,
                            iconPainter = painterResource(id = R.drawable.ic_time),
                            label = "預約時間",
                            title = "$targetDayString $targetTime"
                        )
                    }
                }
            }

            // 調整：寫字板夾子（放大尺寸，並微調 y 軸 offset 以貼合往上移的卡片）
            Image(
                painter = painterResource(id = R.drawable.ic_clip),
                contentDescription = null,
                colorFilter = ColorFilter.tint(Color(0xFF2C4E4E)),
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .offset(y = -3.dp) // 配合卡片上移，將 offset 從 25.dp 調整為 10.dp
                    .size(width = 130.dp, height = 84.dp) // 尺寸放大 (原本 110 x 70)
            )
            /*Image(
                painter = painterResource(id = R.drawable.sheep_2),
                contentDescription = null,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .offset(x = (12).dp, y = (-55).dp)
                    .size(120.dp)
            )*/
        }

        Spacer(modifier = Modifier.height(20.dp))

        // 3. 底部按鈕列
        Column(
            modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(start = 24.dp, end = 24.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // 前往掛號
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .background(color = primaryDark, RoundedCornerShape(20.dp))
                    .clickable {
                        if (isServiceEnabled()) {
                            showConfirmDialog = true
                        } else {
                            showPermissionDialog = true
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Launch, null, tint = Color.White, modifier = Modifier.size(24.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("前往掛號", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Bold)
                }
            }

            // 重新詢問
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .border(
                        width = 1.dp,
                        color = primaryDark.copy(alpha = 0.2f),
                        shape = RoundedCornerShape(20.dp)
                    )
                    .background(
                        color = Color(0xFFD5E5E5).copy(alpha = 0.7f),
                        shape = RoundedCornerShape(20.dp)
                    )
                    .clickable {
                        navController.navigate(Route.CHAT) { popUpTo(Route.HOME) }
                    },
                contentAlignment = Alignment.Center
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "重新詢問",
                        tint = primaryDark,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "重新詢問",
                        color = primaryDark,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }
    }
}

@Composable
fun InfoRowItem(
    icon: ImageVector,
    label: String,
    title: String,
    subLabel: String? = null,
    iconPainter: Painter? = null
) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(modifier = Modifier.weight(1f)) {
            Text(label, fontSize = 14.sp, color = Color(0xFF7A8B8B), fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(4.dp))
            Text(title, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF1A2E2E))
            subLabel?.let { Text(it, fontSize = 15.sp, color = Color(0xFF4A5959)) }
        }
        Spacer(Modifier.width(12.dp))
        if (iconPainter != null) {
            Icon(iconPainter, null, tint = Color(0xFF2C4E4E), modifier = Modifier.size(46.dp))
        } else {
            Icon(icon, null, tint = Color(0xFF2C4E4E), modifier = Modifier.size(46.dp))
        }
    }
}