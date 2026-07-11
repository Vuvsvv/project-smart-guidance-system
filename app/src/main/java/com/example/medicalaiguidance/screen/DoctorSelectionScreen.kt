package com.example.medicalaiguidance.screen

import android.graphics.BitmapFactory
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.MedicalServices
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.medicalaiguidance.model.Doctor
import com.example.medicalaiguidance.model.DoctorProfile
import com.example.medicalaiguidance.navigation.Route
import com.example.medicalaiguidance.network.RecommendationItemDto
import com.example.medicalaiguidance.viewmodel.DoctorRecommendationMode
import com.example.medicalaiguidance.viewmodel.DoctorUiState
import com.example.medicalaiguidance.viewmodel.DoctorViewModel
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DoctorSelectionScreen(
    navController: NavController,
    viewModel: DoctorViewModel = viewModel()
) {
    val primaryDark = Color(0xFF376F72)
    val textDarkColor = Color(0xFF376F72)
    val lightBg = Color(0xFFF2FAF8)      // 背景色

    val uiState by viewModel.uiState.collectAsState()
    val showSheet by viewModel.showBottomSheet.collectAsState()
    val selectedDoctor by viewModel.selectedDoctor.collectAsState()
    val selectedDoctorProfile by viewModel.selectedDoctorProfile.collectAsState()
    val sheetState = rememberModalBottomSheetState()

    if (showSheet && selectedDoctor != null) {
        ModalBottomSheet(
            onDismissRequest = { viewModel.dismissBottomSheet() },
            sheetState = sheetState,
            containerColor = Color.White,
            shape = RoundedCornerShape(topStart = 36.dp, topEnd = 36.dp),
            dragHandle = null
        ) {
            DoctorSpecialtyContent(
                doctor = selectedDoctor!!,
                profile = selectedDoctorProfile,
                onClose = { viewModel.dismissBottomSheet() }
            )
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(lightBg)
    ) {
        // 1. 修改後的同色 HeaderBar
        HeaderBar(
            textDarkColor = textDarkColor,
            onBack = {
                navController.popBackStack()
            }
        )

        when (val state = uiState) {
            DoctorUiState.Loading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = primaryDark)
                }
            }

            is DoctorUiState.Error -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(text = "載入醫師失敗：${state.message}", color = Color(0xFFB00020))
                }
            }

            is DoctorUiState.Success -> {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .navigationBarsPadding(),
                    contentPadding = PaddingValues(
                        start = 24.dp,
                        top = 12.dp,
                        end = 24.dp,
                        bottom = 112.dp
                    ),
                    verticalArrangement = Arrangement.spacedBy(20.dp) // 加寬卡片間距
                ) {
                    item {
                        Column(verticalArrangement = Arrangement.spacedBy(15.dp)) {
                            FilterSummaryCard(
                                primaryDark = primaryDark,
                                mode = state.mode
                            )
                            Text(
                                text = "班表更新可能有誤差，實際名額以醫院當下系統為準。",
                                color = Color(0xFF738286),
                                fontSize = 14.sp,
                                lineHeight = 19.sp,
                                fontWeight =FontWeight.Medium,
                                textAlign = TextAlign.Center,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 4.dp)
                            )
                        }
                    }

                    if (state.recommendations.isNotEmpty()) {
                        items(state.recommendations, key = { it.recommendationId }) { recommendation ->
                            RecommendationDoctorCard(
                                recommendation = recommendation,
                                mode = state.mode,
                                primaryDark = primaryDark,
                                showSpecialtyButton = recommendation.doctor in state.profiledDoctorNames,
                                onCardClick = {
                                    viewModel.selectRecommendationAndNavigate(recommendation) {
                                        navController.navigate(Route.CONFIRM_NEED)
                                    }
                                },
                                onSpecialtyClick = {
                                    viewModel.onRecommendationSpecialtyClick(recommendation)
                                }
                            )
                        }
                    } else {
                        items(state.doctors, key = { it.id }) { doctor ->
                            DoctorCard(
                                doctor = doctor,
                                isRecommended = doctor.id == "doc_02",
                                primaryDark = primaryDark,
                                departmentLabel = state.departmentLabel,
                                showSpecialtyButton = doctor.name in state.profiledDoctorNames,
                                onCardClick = {
                                    viewModel.selectDoctorAndNavigate(doctor) {
                                        navController.navigate(Route.CONFIRM_NEED)
                                    }
                                },
                                onSpecialtyClick = {
                                    viewModel.onDoctorSpecialtyClick(doctor)
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

// 2. 修改 HeaderBar：移除背景色，透出底色
@Composable
private fun HeaderBar(
    textDarkColor: Color,
    onBack: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp, vertical = 20.dp)
            .statusBarsPadding()
            .height(48.dp),
        contentAlignment = Alignment.Center
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.CenterStart)
                .size(48.dp)
                .shadow(elevation = 4.dp, shape = RoundedCornerShape(16.dp))
                .background(Color.White, shape = RoundedCornerShape(16.dp))
                .clickable(onClick = onBack),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "返回",
                tint = textDarkColor,
                modifier = Modifier.size(22.dp)
            )
        }

        Text(
            text = "選擇醫師",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            color = textDarkColor,
            modifier = Modifier.align(Alignment.Center)
        )
    }
}

// 3. 調整篩選橫幅 (FilterSummaryCard)
@Composable
private fun FilterSummaryCard(
    primaryDark: Color,
    mode: DoctorRecommendationMode
) {
    val modeTitle = if (mode == DoctorRecommendationMode.SPECIALTY_FIRST) "科別優先" else "時間優先"
    val subtitle = if (mode == DoctorRecommendationMode.SPECIALTY_FIRST) "符合症狀的建議科別" else "最快可看診的時段"

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(132.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFDCEFEA)),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        // 使用 Box 處理元件間的「上下層壓線」疊加效果
        Box(
            modifier = Modifier.fillMaxSize()
        ) {
            Icon(
                imageVector = if (mode == DoctorRecommendationMode.SPECIALTY_FIRST) Icons.Filled.MedicalServices else Icons.Default.Schedule,
                contentDescription = null,
                // 背景浮水印感
                tint = Color(0xFFABCBC4).copy(alpha = 0.5f),
                modifier = Modifier
                    .align(Alignment.BottomEnd) // 靠右下角定位
                    .offset(x = (12).dp, y = (12).dp) // 稍微往右下偏移，讓它像切邊一樣自然
                    .size(100.dp) // 稍微縮小一點點，因為少了外框，純 Icon 太大會顯得突兀
            )


            // ==========================================
            // 【頂層層級】上方的篩選條件長條標籤
            // ==========================================
            Surface(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .fillMaxWidth() // 撐滿左右
                    .padding(horizontal = 14.dp, vertical = 14.dp), // 透過 padding 留出外圈綠色大框
                shape = RoundedCornerShape(16.dp), // 標籤本身的圓角
                color = Color.White.copy(alpha = 0.7f) // 70% 透明度白
            ) {
                Box(
                    modifier = Modifier.fillMaxWidth(),
                    contentAlignment = Alignment.Center // 文字絕對置中
                ) {
                    Text(
                        text = "您目前的篩選條件：【$modeTitle】",
                        fontSize = 16.sp,
                        color = primaryDark,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(vertical = 10.dp) // 撐出標籤的上下高度
                    )
                }
            }

            // ==========================================
            // 【文字層級】左下方的排序說明文字
            // ==========================================
            Column(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 24.dp, bottom = 18.dp)
            ) {
                Text(
                    text = "已為您排序",
                    fontSize = 15.sp,
                    color = Color(0xFF4C5A5A),
                    fontWeight = FontWeight.Medium
                )

                Spacer(modifier = Modifier.height(2.dp))

                Text(
                    text = subtitle,
                    fontSize = 20.sp, // 字體放大，強化粗體對比
                    fontWeight = FontWeight.SemiBold,
                    color = Color(0xFF1F3030),
                    letterSpacing = 0.5.sp // 微調字距
                )
            }
        }
    }
}
// RecommendationDoctorCard 經過 AI 運算有帶有「推薦理由」的卡片 (暫時無用)
@Composable
private fun RecommendationDoctorCard(
    recommendation: RecommendationItemDto,
    mode: DoctorRecommendationMode,
    primaryDark: Color,
    showSpecialtyButton: Boolean,
    onCardClick: () -> Unit,
    onSpecialtyClick: () -> Unit
) {
    val isSpecialtyMode = mode == DoctorRecommendationMode.SPECIALTY_FIRST
    val timeText = listOf(recommendation.date, recommendation.slot.ifBlank { recommendation.session })
        .filter { it.isNotBlank() }
        .joinToString(" ")
    val reasonText = recommendation.reasons.firstOrNull()
        ?: if (isSpecialtyMode) "依症狀與建議科別排序" else "依最快可看診時段排序"

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = if (isSpecialtyMode) 210.dp else 188.dp),
        shape = RoundedCornerShape(30.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(22.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size(width = 82.dp, height = 92.dp),
                    shape = RoundedCornerShape(16.dp),
                    color = Color(0xFFE1E8E8)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.Person,
                            contentDescription = null,
                            tint = primaryDark,
                            modifier = Modifier.size(38.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.width(16.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = recommendation.doctor.ifBlank { "推薦醫師" },
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF1F3030),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f)
                        )
                        if (recommendation.isBestMatch || recommendation.rank == 1) {
                            Spacer(modifier = Modifier.width(8.dp))
                            Surface(
                                shape = RoundedCornerShape(50),
                                color = Color(0xFFFDF6EC)
                            ) {
                                Text(
                                    text = if (isSpecialtyMode) "科別首選" else "最快推薦",
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFFE6A23C),
                                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = recommendation.childDept.ifBlank { recommendation.parentDept },
                        color = Color(0xFF607575),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )

                    if (timeText.isNotBlank()) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.CalendarToday,
                                contentDescription = null,
                                tint = primaryDark,
                                modifier = Modifier.size(15.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = if (isSpecialtyMode) "可看診：$timeText" else "最快看診：$timeText",
                                color = primaryDark,
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 14.sp
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = if (isSpecialtyMode) Color(0xFFF0F8F6) else Color(0xFFFFF8EF)
            ) {
                Text(
                    text = reasonText,
                    color = if (isSpecialtyMode) primaryDark else Color(0xFF8A5A1F),
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (showSpecialtyButton) {
                    Surface(
                        modifier = Modifier
                            .weight(1f)
                            .height(46.dp)
                            .clickable(onClick = onSpecialtyClick),
                        shape = RoundedCornerShape(14.dp),
                        color = Color.White,
                        border = BorderStroke(1.dp, primaryDark)
                    ) {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("醫師簡介", color = primaryDark, fontWeight = FontWeight.Bold)
                        }
                    }
                }

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(46.dp)
                        .background(primaryDark, RoundedCornerShape(14.dp))
                        .clickable(onClick = onCardClick),
                    contentAlignment = Alignment.Center
                ) {
                    Text("我要掛號", color = Color.White, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

//  4. 調整醫師卡片的圓角與內部高度間距
@Composable
private fun DoctorCard(
    doctor: Doctor,
    isRecommended: Boolean,
    primaryDark: Color,
    departmentLabel: String?,
    showSpecialtyButton: Boolean,
    onCardClick: () -> Unit,
    onSpecialtyClick: () -> Unit
) {
    val firstSlot = doctor.availableSlots.firstOrNull()

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 180.dp),
        shape = RoundedCornerShape(30.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp) // 陰影稍微放輕
    ) {
        Column(modifier = Modifier.padding(22.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size(width = 82.dp, height = 92.dp),
                    shape = RoundedCornerShape(16.dp), // 大圓角大頭照容器
                    color = Color(0xFFE1E8E8)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.Person,
                            contentDescription = null,
                            tint = primaryDark,
                            modifier = Modifier.size(38.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.width(16.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = doctor.name,
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF1F3030),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f)
                        )
                        if (isRecommended) {
                            Spacer(modifier = Modifier.width(8.dp))
                            Surface(
                                shape = RoundedCornerShape(50),
                                color = Color(0xFFFDF6EC)
                            ) {
                                Text(
                                    text = "推薦選擇",
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFFE6A23C),
                                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = departmentLabel ?: doctor.title,
                        color = Color(0xFF607575),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    if (firstSlot != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.CalendarToday,
                                contentDescription = null,
                                tint = primaryDark,
                                modifier = Modifier.size(15.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "最快看診：${firstSlot.first} ${firstSlot.second}",
                                color = primaryDark,
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 14.sp
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 下方按鈕區：微調按鈕圓角
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (showSpecialtyButton) {
                    Surface(
                        modifier = Modifier
                            .weight(1f)
                            .height(46.dp)
                            .clickable(onClick = onSpecialtyClick),
                        shape = RoundedCornerShape(14.dp),
                        color = Color.White,
                        border = BorderStroke(1.dp, primaryDark)
                    ) {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("醫師簡介", color = primaryDark, fontWeight = FontWeight.Bold)
                        }
                    }
                }
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(46.dp)
                        .background(primaryDark, RoundedCornerShape(14.dp))
                        .clickable(onClick = onCardClick),
                    contentAlignment = Alignment.Center
                ) {
                    Text("我要掛號", color = Color.White, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

//底部簡介視窗內容 (DoctorSpecialtyContent)
@Composable
private fun DoctorSpecialtyContent(
    doctor: Doctor,
    profile: DoctorProfile?,
    onClose: () -> Unit
) {
    val accentOrange = Color(0xFFE58A2A)
    val textDark = Color(0xFF151515)
    val configuration = LocalConfiguration.current
    val maxSheetHeight = (configuration.screenHeightDp * 0.8f).dp
    var showExperience by remember { mutableStateOf(false) }
    val titleText = profile?.titles?.takeIf { it.isNotEmpty() }?.joinToString("、") ?: doctor.title
    val educationItems = profile?.education?.takeIf { it.isNotEmpty() } ?: listOf("暫無學歷資料")
    val specialtyItems = profile?.specialtyTags?.takeIf { it.isNotEmpty() }
        ?: doctor.specialties.mapIndexed { index, specialty ->
            specialty.trimStart().removePrefix("${index + 1}.").trim()
        }
    val experienceItems = buildList {
        profile?.currentPositions?.takeIf { it.isNotEmpty() }?.let { positions ->
            add("現職")
            addAll(positions)
        }
        profile?.experience?.takeIf { it.isNotEmpty() }?.let { experience ->
            add("經歷")
            addAll(experience)
        }
    }

    // 外層主容器（固定抽屜最大高度）
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(max = maxSheetHeight)
            .background(Color.White)
    ) {
        // ==========================================
        // 1. 極簡橫幅：僅保留抽屜頂部的小灰色裝飾橫條
        // ==========================================
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(20.dp),
            contentAlignment = Alignment.TopCenter
        ) {
            Box(
                modifier = Modifier
                    .padding(top = 10.dp)
                    .size(width = 40.dp, height = 4.dp)
                    .background(Color(0xFFD8D8D8), RoundedCornerShape(50))
            )
        }

        // ==========================================
        // 2. 姓名、職稱、關閉按鈕「橫向」固定列
        // ==========================================
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 34.dp, end = 24.dp, top = 20.dp, bottom = 12.dp), // 調整右邊距配合按鈕
            verticalAlignment = Alignment.CenterVertically // 確保整排元件垂直居中對齊
        ) {
            // 【最左邊】醫師姓名
            Text(
                text = doctor.name,
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
                color = textDark
            )

            Spacer(modifier = Modifier.width(12.dp))

            // 【中間】職稱：利用 weight(1f) 自動填滿剩餘空間，並將關閉按鈕推向最右側
            Text(
                text = titleText,
                fontSize = 15.sp,
                fontWeight = FontWeight.Medium,
                color = Color(0xFF666666), // 灰黑色，做出視覺層次
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f) // 推開關閉按鈕的關鍵彈簧
            )

            Spacer(modifier = Modifier.width(12.dp))

            // 【最右邊】關閉按鈕
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .background(Color(0xFFE8E8E8), CircleShape)
                    .clickable(onClick = onClose),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Close,
                    contentDescription = "關閉",
                    tint = Color(0xFF222222),
                    modifier = Modifier.size(18.dp)
                )
            }
        }

        // ==========================================
        // 捲動區域：大頭照、學歷、專長與經歷
        // ==========================================
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f) //  關鍵：讓可捲動區吃滿剩下的空間
                .verticalScroll(rememberScrollState()) // 獨立滾動掛
                .padding(horizontal = 34.dp)
                .padding(top = 16.dp, bottom = 42.dp)
        ) {
            // 大頭照與學歷資訊
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Top
            ) {
                // 左側大頭照
                Box(
                    modifier = Modifier
                        .size(width = 88.dp, height = 98.dp)
                        .background(Color(0xFFD8D8D8), RoundedCornerShape(12.dp))
                        .clip(RoundedCornerShape(12.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    DoctorPhoto(
                        photoUrl = profile?.photoUrl ?: doctor.imageUrl,
                        modifier = Modifier.fillMaxSize()
                    )
                }

                Spacer(modifier = Modifier.width(20.dp))

                // 右側學歷
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.School,
                            contentDescription = null,
                            tint = Color.Black,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "學歷",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = textDark
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    educationItems.forEach { item ->
                        Text(
                            text = item,
                            fontSize = 14.sp,
                            lineHeight = 22.sp,
                            color = textDark,
                            modifier = Modifier.padding(bottom = 4.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // 專長區塊
            SectionPill(
                    icon = {
                        Icon(
                            imageVector = Icons.Default.ThumbUp,
                            contentDescription = null,
                            tint = accentOrange,
                            modifier = Modifier.size(22.dp)
                        )
                    },
                    title = "專長",
                    accentColor = accentOrange
                )

                Spacer(modifier = Modifier.height(14.dp))

                ProfileBulletList(
                    items = specialtyItems,
                    textDark = textDark
                )

            Spacer(modifier = Modifier.height(32.dp))

            // 經歷區塊
            SectionPill(
                icon = {
                    Icon(
                        imageVector = Icons.Default.Person,
                        contentDescription = null,
                        tint = accentOrange,
                        modifier = Modifier.size(22.dp)
                    )
                },
                title = "經歷",
                accentColor = accentOrange,
                trailing = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = if (showExperience) "收合" else "查看",
                            color = accentOrange,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Icon(
                            imageVector = if (showExperience) {
                                Icons.Default.KeyboardArrowUp
                            } else {
                                Icons.Default.KeyboardArrowDown
                            },
                            contentDescription = null,
                            tint = accentOrange,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                },
                onClick = { showExperience = !showExperience }
            )

            if (showExperience) {
                Spacer(modifier = Modifier.height(14.dp))
                Column(
                    modifier = Modifier.padding(start = 28.dp, end = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    if (experienceItems.isEmpty()) {
                        Text(
                            text = "暫無經歷資料",
                            color = textDark,
                            fontSize = 15.sp,
                            lineHeight = 22.sp
                        )
                    } else {
                        val groupedItems = experienceItems.fold(
                            mutableListOf<Pair<String, MutableList<String>>>()
                        ) { groups, item ->
                            if (item == "現職" || item == "經歷") {
                                groups.add(item to mutableListOf())
                            } else {
                                if (groups.isEmpty()) groups.add("" to mutableListOf())
                                groups.last().second.add(item)
                            }
                            groups
                        }

                        groupedItems.forEach { (title, items) ->
                            if (title.isNotBlank()) {
                                Text(
                                    text = title,
                                    color = textDark,
                                    fontSize = 16.sp,
                                    lineHeight = 22.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            ProfileBulletList(
                                items = items,
                                textDark = textDark,
                                contentPadding = PaddingValues(0.dp),
                                fontSize = 14.sp,
                                lineHeight = 22.sp,
                                itemSpacing = 6.dp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }
            }
    }
}
}

//ProfileBulletList 繪製帶有點點（•）的清單
@Composable
private fun ProfileBulletList(
    items: List<String>,
    textDark: Color,
    contentPadding: PaddingValues = PaddingValues(start = 28.dp, end = 8.dp),
    fontSize: androidx.compose.ui.unit.TextUnit = 16.sp,
    lineHeight: androidx.compose.ui.unit.TextUnit = 28.sp,
    itemSpacing: androidx.compose.ui.unit.Dp = 14.dp,
    fontWeight: FontWeight = FontWeight.SemiBold
) {
    Column(
        modifier = Modifier.padding(contentPadding),
        verticalArrangement = Arrangement.spacedBy(itemSpacing)
    ) {
        items.filter { it.isNotBlank() }.forEach { item ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Top
            ) {
                Text(
                    text = "•",
                    color = textDark,
                    fontSize = fontSize,
                    lineHeight = lineHeight,
                    fontWeight = fontWeight,
                    modifier = Modifier.width(20.dp)
                )
                Text(
                    text = item,
                    color = textDark,
                    fontSize = fontSize,
                    lineHeight = lineHeight,
                    fontWeight = fontWeight,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

//DoctorPhoto 負責從網路下載圖片
@Composable
private fun DoctorPhoto(
    photoUrl: String?,
    modifier: Modifier = Modifier
) {
    val imageBitmap by produceState<androidx.compose.ui.graphics.ImageBitmap?>(null, photoUrl) {
        value = null
        if (photoUrl.isNullOrBlank()) return@produceState
        value = withContext(Dispatchers.IO) {
            runCatching {
                URL(photoUrl).openStream().use { stream ->
                    BitmapFactory.decodeStream(stream)?.asImageBitmap()
                }
            }.getOrNull()
        }
    }

    if (imageBitmap != null) {
        Image(
            bitmap = imageBitmap!!,
            contentDescription = null,
            modifier = modifier,
            contentScale = ContentScale.Crop
        )
    } else {
        Box(
            modifier = modifier.background(Color(0xFFD8D8D8)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Person,
                contentDescription = null,
                tint = Color(0xFF9A9A9A),
                modifier = Modifier.size(42.dp)
            )
        }
    }
}

//SectionPill 橘色的圓條標題（如“專長”、“經歷”）
@Composable
private fun SectionPill(
    icon: @Composable () -> Unit,
    title: String,
    accentColor: Color,
    trailing: @Composable (() -> Unit)? = null,
    onClick: (() -> Unit)? = null
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .height(48.dp)
            .shadow(
                elevation = 1.5.dp,
                shape = RoundedCornerShape(24.dp),
                ambientColor = Color.Black.copy(alpha = 0.04f),
                spotColor = Color.Black.copy(alpha = 0.06f)
            )
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
        shape = RoundedCornerShape(24.dp),
        color = Color(0xFFFFF8F1)
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(start = 18.dp, end = 18.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            icon()
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                text = title,
                color = accentColor,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.weight(1f))
            trailing?.invoke()
        }
    }
}
