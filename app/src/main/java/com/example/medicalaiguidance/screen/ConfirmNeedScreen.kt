package com.example.medicalaiguidance.screen

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
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

    // 控制提醒彈窗與權限
    var showPermissionDialog by remember { mutableStateOf(false) }
    var showConfirmDialog by remember { mutableStateOf(false) }

    // 是否開啟智慧導引功能 (預設為開啟)
    var isGuidanceEnabled by remember { mutableStateOf(true) }

    // 控制「小羊氣泡選單」的顯示狀態 (點擊小羊開關)
    var showGuidanceBubble by remember { mutableStateOf(false) }

    val primaryDark = Color(0xFF376F72)
    val badgeBg = Color(0xFFD9EAE7)
    val bgGradient = Brush.verticalGradient(colors = listOf(Color(0xFFF2FAF8), Color(0xFFF2FAF8)))

    val fontScale = LocalDensity.current.fontScale
    val cardMinHeight = when {
        fontScale >= 1.3f -> 480.dp
        fontScale >= 1.15f -> 440.dp
        else -> 400.dp
    }
    val cardMaxHeight = when {
        fontScale >= 1.3f -> 600.dp
        fontScale >= 1.15f -> 540.dp
        else -> 480.dp
    }
    val infoContentMaxHeight = when {
        fontScale >= 1.3f -> 410.dp
        fontScale >= 1.15f -> 360.dp
        else -> 300.dp
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

    // 1. 權限開啟提醒彈窗
    if (showPermissionDialog) {
        AlertDialog(
            onDismissRequest = { showPermissionDialog = false },
            shape = RoundedCornerShape(24.dp),
            containerColor = Color.White,
            title = {
                Text(
                    text = "開啟紅框引導功能",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF1A2E2E)
                )
            },
            text = {
                Text(
                    text = "為了讓系統能在台北榮總 App 顯示「紅框引導」，請至手機「設定」>「協助工具」中開啟「Medical AI Guidance」。",
                    fontSize = 15.sp,
                    lineHeight = 22.sp,
                    color = Color(0xFF556666)
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
                            .clip(RoundedCornerShape(24.dp))
                            .clickable { showPermissionDialog = false },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "取消", color = Color(0xFF7A8B8B), fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
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

    // 2. 再次確認視窗 (準備跳轉)
    if (showConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showConfirmDialog = false },
            shape = RoundedCornerShape(24.dp),
            containerColor = Color.White,
            title = {
                Text(
                    text = "再次確認",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF1A2E2E)
                )
            },
            text = {
                Text(
                    text = if (isGuidanceEnabled) "即將前往台北榮總 App，並啟動紅框輔助引導。" else "即將前往台北榮總 App 自行進行掛號。",
                    fontSize = 15.sp,
                    lineHeight = 22.sp,
                    color = Color(0xFF556666)
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
                            .clip(RoundedCornerShape(24.dp))
                            .clickable { showConfirmDialog = false },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "取消", color = Color(0xFF7A8B8B), fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp)
                            .background(color = primaryDark, RoundedCornerShape(24.dp))
                            .clip(RoundedCornerShape(24.dp))
                            .clickable {
                                showConfirmDialog = false

                                if (isGuidanceEnabled) {
                                    MyAccessibilityService.updateTarget(
                                        department = targetDept,
                                        clinic = targetClinic,
                                        doctor = targetDoctor,
                                        date = currentApt.date,
                                        timeSlot = targetTime
                                    )
                                }

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
        // 頂部導航列
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

        // 核心大卡片與小羊互動區塊
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f, fill = false)
                .padding(horizontal = 24.dp, vertical = 4.dp)
        ) {
            // 吉祥物小羊 (純視覺，無點擊事件)
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .offset(x = (12).dp, y = (-55).dp)
            ) {
                Image(
                    painter = painterResource(id = R.drawable.sheep_2),
                    contentDescription = "安心陪伴者",
                    modifier = Modifier
                        .size(110.dp)
                        .clip(CircleShape)
                )
            }

            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 28.dp)
                    .heightIn(min = cardMinHeight, max = cardMaxHeight)
                    .shadow(2.dp, RoundedCornerShape(30.dp))
                    .border(width = 10.dp, color = badgeBg.copy(alpha = 0.8f), shape = RoundedCornerShape(30.dp)),
                shape = RoundedCornerShape(30.dp),
                colors = CardDefaults.cardColors(containerColor = Color.White)
            ) {
                // 關鍵1：讓 Column 填滿 Card，方便我們進行三段式佈局 (頭、身、尾)
                Column(modifier = Modifier.fillMaxSize()) {

                    // [頭] 標題區塊 (固定)
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 36.dp, bottom = 12.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Box(
                            modifier = Modifier
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
                    }

                    // [身] 資訊區塊 (可滑動)
                    // 關鍵2：使用 weight(1f) 讓此區塊佔據中間所有剩餘空間
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f)
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = 28.dp, vertical = 8.dp),
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

                    // [尾] 導引設定區塊 (固定在卡片最下方)
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFFF9FCFC)) // 上一點極淡的底色增加層次
                    ) {
                        HorizontalDivider(color = Color(0xFFEBF2F2), thickness = 1.dp)
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 24.dp, vertical = 16.dp)
                                .padding(bottom = 8.dp), // 配合邊框給予適當的底部留白
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.weight(1f)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.TipsAndUpdates,
                                    contentDescription = null,
                                    tint = primaryDark,
                                    modifier = Modifier.size(26.dp)
                                )
                                Spacer(modifier = Modifier.width(10.dp))
                                Column {
                                    Text(
                                        text = "啟用紅框智慧導引",
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = primaryDark
                                    )
                                    Spacer(modifier = Modifier.height(2.dp))
                                    Text(
                                        text = if (isGuidanceEnabled) "在榮總 App 顯示紅框提示步驟" else "直接開啟榮總 App 自行操作",
                                        fontSize = 12.sp,
                                        color = Color(0xFF556666)
                                    )
                                }
                            }
                            Switch(
                                checked = isGuidanceEnabled,
                                onCheckedChange = { isGuidanceEnabled = it },
                                colors = SwitchDefaults.colors(
                                    checkedThumbColor = Color.White,
                                    checkedTrackColor = primaryDark,
                                    uncheckedThumbColor = Color.White,
                                    uncheckedTrackColor = Color(0xFFB0C4C4),
                                    uncheckedBorderColor = Color.Transparent
                                )
                            )
                        }
                    }
                }
            }

            // 上方的迴紋針裝飾
            Image(
                painter = painterResource(id = R.drawable.ic_clip),
                contentDescription = null,
                colorFilter = ColorFilter.tint(Color(0xFF2C4E4E)),
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .offset(y = (-3).dp)
                    .size(width = 130.dp, height = 84.dp)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // 底部按鈕區塊
        Column(
            modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(start = 24.dp, end = 24.dp, bottom = 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // 前往掛號按鈕
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
                    .background(color = primaryDark, RoundedCornerShape(20.dp))
                    .clickable {
                        if (isGuidanceEnabled) {
                            if (isServiceEnabled()) {
                                showConfirmDialog = true
                            } else {
                                showPermissionDialog = true
                            }
                        } else {
                            showConfirmDialog = true
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

            // 重新詢問按鈕
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
