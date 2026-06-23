//package com.example.medicalaiguidance.screen
//
//import androidx.compose.foundation.BorderStroke
//import androidx.compose.foundation.background
//import androidx.compose.foundation.layout.*
//import androidx.compose.foundation.shape.CircleShape
//import androidx.compose.foundation.shape.RoundedCornerShape
//import androidx.compose.material.icons.Icons
//import androidx.compose.material.icons.filled.Mic
//import androidx.compose.material.icons.filled.Waves
//import androidx.compose.material3.*
//import androidx.compose.runtime.Composable
//import androidx.compose.ui.Alignment
//import androidx.compose.ui.Modifier
//import androidx.compose.ui.graphics.Color
//import androidx.compose.ui.text.font.FontWeight
//import androidx.compose.ui.unit.dp
//import androidx.compose.ui.unit.sp
//import androidx.navigation.NavController
//import com.example.medicalaiguidance.navigation.Route
//import androidx.compose.foundation.Canvas
//import androidx.compose.ui.graphics.drawscope.Stroke
//import androidx.compose.material.icons.filled.GraphicEq
//
//@Deprecated("Legacy prototype screen. Current main flow starts from HelpScreen and calls backend /chat directly.")
//@Composable
//fun VoiceInput1Screen(navController: NavController) {
//    val primaryDark = Color(0xFF3E6666)
//    val ringColor = Color(0xFFB0CECE)
//
//    Column(
//        modifier = Modifier
//            .fillMaxSize()
//            .background(Color.White)
//            .padding(horizontal = 32.dp),
//        horizontalAlignment = Alignment.CenterHorizontally
//    ) {
//        Spacer(modifier = Modifier.height(80.dp))
//
//        // 聽取中文字
//        Text(
//            text = "聽取中...",
//            fontSize = 28.sp,
//            fontWeight = FontWeight.Bold,
//            color = Color.Black
//        )
//
//        Spacer(modifier = Modifier.weight(1f))
//
//        // 語音波形圓環區塊
//        Box(
//            contentAlignment = Alignment.BottomCenter,
//            modifier = Modifier.size(280.dp)
//        ) {
//            // 外圈淡色環
//            Canvas(modifier = Modifier.size(280.dp)) {
//                drawCircle(
//                    color = ringColor.copy(alpha = 0.3f),
//                    radius = size.minDimension / 2,
//                    style = Stroke(width = 6.dp.toPx())
//                )
//            }
//
//            // 主圓圈
//            Surface(
//                modifier = Modifier
//                    .size(230.dp)
//                    .align(Alignment.Center),
//                shape = CircleShape,
//                border = BorderStroke(6.dp, ringColor),
//                color = Color(0xFFF0F5F5)
//            ) {
//                Box(contentAlignment = Alignment.Center) {
//                    Icon(
//                        imageVector = Icons.Default.GraphicEq, // 波形 icon
//                        contentDescription = null,
//                        modifier = Modifier.size(100.dp),
//                        tint = primaryDark
//                    )
//                }
//            }
//
//            // 麥克風按鈕（疊在圓底部）
//            FloatingActionButton(
//                onClick = { navController.navigate(Route.VOICE_INPUT_2) },
//                containerColor = primaryDark,
//                shape = CircleShape,
//                modifier = Modifier
//                    .size(64.dp)
//                    .align(Alignment.BottomCenter)
//                    .offset(y = 20.dp)
//            ) {
//                Icon(
//                    Icons.Default.Mic,
//                    contentDescription = null,
//                    tint = Color.White,
//                    modifier = Modifier.size(28.dp)
//                )
//            }
//        }
//
//        Spacer(modifier = Modifier.weight(1f))
//
//        // 取消按鈕
//        OutlinedButton(
//            onClick = { navController.popBackStack() },
//            shape = RoundedCornerShape(16.dp),
//            border = BorderStroke(1.dp, Color(0xFFD0D0D0)),
//            modifier = Modifier
//                .width(160.dp)
//                .height(52.dp)
//        ) {
//            Text("✕  取消", color = Color.Gray, fontSize = 16.sp)
//        }
//
//        Spacer(modifier = Modifier.height(60.dp))
//    }
//}
