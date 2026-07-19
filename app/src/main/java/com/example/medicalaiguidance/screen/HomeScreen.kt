package com.example.medicalaiguidance.screen


import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MedicalServices
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.navigation.NavHostController
import com.example.medicalaiguidance.R
import com.example.medicalaiguidance.model.HistoryStatus
import com.example.medicalaiguidance.navigation.Route
import com.example.medicalaiguidance.viewmodel.HomeViewModel
import androidx.compose.ui.draw.alpha
@Composable
fun HomeScreen(
    navController: NavHostController,
    homeViewModel: HomeViewModel = viewModel()
) {
    val recentHistory by homeViewModel.recentHistory.collectAsState()
    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                homeViewModel.fetchRecentHistory()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    val textDarkColor = Color(0xFF1A2E2E)
    val primaryDark = Color(0xFF385E5E)

    val homeBackgroundGradient = Brush.linearGradient(
        colors = listOf(
            Color(0xFFE8F2F0),
            Color(0xFFFBFCFC),
            Color(0xFFE4EFED)
        ),
        start = Offset(0f, 0f),
        end = Offset(900f, 1800f)
    )

    val buttonGradient = Brush.verticalGradient(
        colors = listOf(Color(0xFF6E9999), Color(0xFF036A6D))
    )

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(homeBackgroundGradient)
            .statusBarsPadding(),
        contentPadding = PaddingValues(start = 28.dp, end = 28.dp, bottom = 24.dp)
    ) {
        item {
            Spacer(modifier = Modifier.height(24.dp))

            // 問候氣泡框與大按鈕用 Box 包起來，跨元件定位與疊加
            Box(modifier = Modifier.fillMaxWidth()) {

                Column(modifier = Modifier.fillMaxWidth()) {

                    // 1. 問候文字氣泡框
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            /*.background(
                                color = Color.White.copy(alpha = 0.3f), // 70% 透明度白底
                                shape = RoundedCornerShape(
                                    topStart = 32.dp,
                                    topEnd = 32.dp,
                                    bottomEnd = 12.dp, // 讓右下角帶點對話框的切角感
                                    bottomStart = 32.dp
                                )
                            )
                            .padding(horizontal = 24.dp, vertical = 20.dp)*/

                            .padding(top = 12.dp, bottom = 12.dp)
                    ) {
                        Column {
                            Text(
                                text = "Hello",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF4A7373)
                            )

                            Spacer(modifier = Modifier.height(6.dp))

                            Text(
                                text = "今天有什麼可以幫您？",
                                fontSize = 24.sp,
                                fontWeight = FontWeight.Bold,
                                color = textDarkColor
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(15.dp)) // 氣泡與按鈕的間距

                    // 2. 醫療指引大按鈕
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(220.dp)
                            .shadow(
                                elevation = 12.dp,
                                shape = RoundedCornerShape(50.dp),
                                clip = false,
                                ambientColor = Color(0xFF385E5E).copy(alpha = 0.3f),
                                spotColor = Color(0xFF385E5E).copy(alpha = 0.5f)
                            )
                            .background(brush = buttonGradient, shape = RoundedCornerShape(50.dp))
                            .clickable {
                                navController.navigate(Route.CHAT)
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(80.dp)
                                    .background(Color.White.copy(alpha = 0.15f), shape = CircleShape),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.MedicalServices,
                                    contentDescription = null,
                                    tint = Color.White,
                                    modifier = Modifier.size(38.dp)
                                )
                            }

                            Spacer(modifier = Modifier.height(20.dp))

                            Text(
                                text = "開始醫療指引",
                                fontSize = 26.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White,
                                letterSpacing = 2.sp
                            )
                        }
                    }
                }

                // 3. 疊在最上面的小羊（利用 offset 調整微調，壓在按鈕右上角）
                Image(
                    painter = painterResource(id = R.drawable.sheep),
                    contentDescription = null,
                    modifier = Modifier
                        .size(135.dp)
                        .align(Alignment.TopEnd)
                        // x 稍微往外移，y 往下移壓在按鈕的交界處
                        .offset(x = (20).dp, y = (1).dp),
                    contentScale = ContentScale.Fit
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 紅框位置測試
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End
            ) {
                Box(
                    modifier = Modifier
                        .shadow(1.dp, RoundedCornerShape(16.dp))
                        .background(Color.White, RoundedCornerShape(16.dp))
                        .border(1.dp, Color(0xFFE0E8E7), RoundedCornerShape(16.dp))
                        .clickable {
                            navController.navigate(Route.MOCK_SCHEDULE_TEST)
                        }
                        .padding(horizontal = 14.dp, vertical = 8.dp)
                ) {
                    Text(
                        text = "紅框位置測試",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium,
                        color = primaryDark
                    )
                }
            }

            Spacer(modifier = Modifier.height(40.dp))

            // 標題與「查看全部」
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "近期紀錄",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = textDarkColor
                )

                Box(
                    modifier = Modifier
                        .border(
                            width = 1.dp,
                            color = Color(0xFF7A8B8B).copy(alpha = 0.5f),
                            shape = RoundedCornerShape(20.dp)
                        )
                        .background(Color.White, shape = RoundedCornerShape(20.dp))
                        .clickable {
                            navController.navigate(Route.HISTORY)
                        }
                        .padding(horizontal = 14.dp, vertical = 6.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "查看全部",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium,
                        color = Color(0xFF4A7373)
                    )
                }
            }
            Spacer(modifier = Modifier.height(18.dp))
        }

        // 近期紀錄：有資料就渲染清單，沒資料就顯示空狀態
        if (recentHistory.isEmpty()) {
            item {
                EmptyHistoryState()
            }
        } else {
            items(
                items = recentHistory,
                key = { it.id }
            ) { history ->
                RecordItem(
                    date = history.date,
                    summary = if (history.status == HistoryStatus.UNCOMPLETED) "症狀評估中" else history.typeTitle,
                    icon = if (history.status == HistoryStatus.UNCOMPLETED) Icons.Default.Psychology else history.icon,
                    status = history.status,
                    onClick = { navController.navigate(Route.chatHistory(history.id)) }
                )
                Spacer(modifier = Modifier.height(14.dp))
            }
        }
    }
}

@Composable
fun EmptyHistoryState() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .fillMaxHeight()
            .height(280.dp)
            .padding(horizontal = 16.dp, vertical = 24.dp) // 避免在平板上直接貼齊邊緣
            .border(
                width = 2.dp,
                color = Color(0xFFD9EAE7),
                shape = RoundedCornerShape(36.dp)
            ),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Image(
                painter = painterResource(id = R.drawable.sheep_3),
                contentDescription = null,
                modifier = Modifier.size(120.dp)
                .alpha(0.5f),
                contentScale = ContentScale.Fit
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "暫無紀錄",
                fontSize = 16.sp,
                fontWeight = FontWeight.Medium,
                color = Color(0xFF7A8B8B)
            )
        }
    }
}

@Composable
fun RecordItem(
    date: String,
    summary: String,
    icon: ImageVector,
    status: HistoryStatus,
    onClick: () -> Unit
) {
    val isUncompleted = status == HistoryStatus.UNCOMPLETED

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(
                elevation = 4.dp,
                shape = RoundedCornerShape(45.dp),
                ambientColor = Color.Black.copy(alpha = 0.05f),
                spotColor = Color.Black.copy(alpha = 0.05f)
            )
            .background(Color.White, shape = RoundedCornerShape(45.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 28.dp, vertical = 28.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 圖標圓圈
        Box(
            modifier = Modifier
                .size(52.dp)
                .background(Color(0xFFF0F5F5), shape = CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = Color(0xFF036A6D),
                modifier = Modifier.size(26.dp)
            )
        }

        Spacer(modifier = Modifier.width(16.dp))

        // 文字資訊
        Column(
            modifier = Modifier.weight(1f)
        ) {
            Text(
                text = date,
                fontSize = 14.sp,
                color = Color(0xFF7A8B8B),
                fontWeight = FontWeight.Medium
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = summary,
                fontSize = 18.sp,
                color = Color(0xFF1A2E2E),
                fontWeight = FontWeight.Bold
            )
        }

        // 狀態 Badge (未完成/已完成)
        Surface(
            color = if (isUncompleted) Color(0xFFFDF6EC) else Color(0xFFD1E9E3),
            shape = RoundedCornerShape(12.dp)
        ) {
            Text(
                text = if (isUncompleted) "未完成" else "已完成",
                color = if (isUncompleted) Color(0xFFE6A23C) else Color(0xFF385E5E),
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
            )
        }
    }
}