package com.example.medicalaiguidance.screen

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.medicalaiguidance.model.Doctor
import com.example.medicalaiguidance.navigation.Route
import com.example.medicalaiguidance.viewmodel.DoctorUiState
import com.example.medicalaiguidance.viewmodel.DoctorViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DoctorSelectionScreen(
    navController: NavController,
    viewModel: DoctorViewModel = viewModel()
) {
    val primaryDark = Color(0xFF376F72)
    val lightBg = Color(0xFFF2FAF8)
    val uiState by viewModel.uiState.collectAsState()
    val showSheet by viewModel.showBottomSheet.collectAsState()
    val selectedDoctor by viewModel.selectedDoctor.collectAsState()
    val sheetState = rememberModalBottomSheetState()

    if (showSheet && selectedDoctor != null) {
        ModalBottomSheet(
            onDismissRequest = { viewModel.dismissBottomSheet() },
            sheetState = sheetState,
            containerColor = Color.White,
            shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)
        ) {
            DoctorSpecialtyContent(doctor = selectedDoctor!!)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(lightBg)
    ) {
        HeaderBar(
            primaryDark = primaryDark,
            onBack = {
                navController.navigate(Route.CHAT) {
                    popUpTo(Route.SELECT_DOCTOR) { inclusive = true }
                    launchSingleTop = true
                }
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
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 24.dp, vertical = 22.dp),
                    verticalArrangement = Arrangement.spacedBy(18.dp)
                ) {
                    items(state.doctors, key = { it.id }) { doctor ->
                        DoctorCard(
                            doctor = doctor,
                            isRecommended = doctor.id == "doc_02",
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

@Composable
private fun HeaderBar(
    primaryDark: Color,
    onBack: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(130.dp)
            .background(
                color = primaryDark,
                shape = RoundedCornerShape(bottomStart = 28.dp, bottomEnd = 28.dp)
            )
            .statusBarsPadding()
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(start = 24.dp)
                .size(48.dp)
                .background(Color.White, RoundedCornerShape(16.dp))
                .clickable(onClick = onBack),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "返回",
                tint = primaryDark
            )
        }

        Text(
            text = "選擇醫師",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White,
            modifier = Modifier.align(Alignment.Center)
        )
    }
}

@Composable
private fun DoctorCard(
    doctor: Doctor,
    isRecommended: Boolean,
    onCardClick: () -> Unit,
    onSpecialtyClick: () -> Unit
) {
    val primaryDark = Color(0xFF376F72)
    val firstSlot = doctor.availableSlots.firstOrNull()

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 168.dp),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size(width = 82.dp, height = 92.dp),
                    shape = RoundedCornerShape(14.dp),
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
                            Text(
                                text = "推薦",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFFE67E22)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = doctor.title,
                        color = Color(0xFF607575),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    if (firstSlot != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "${firstSlot.first} ${firstSlot.second}",
                            color = primaryDark,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(44.dp)
                        .background(Color(0xFFE9F5F3), RoundedCornerShape(10.dp))
                        .clickable(onClick = onSpecialtyClick),
                    contentAlignment = Alignment.Center
                ) {
                    Text("專長", color = primaryDark, fontWeight = FontWeight.Bold)
                }
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(44.dp)
                        .background(primaryDark, RoundedCornerShape(10.dp))
                        .clickable(onClick = onCardClick),
                    contentAlignment = Alignment.Center
                ) {
                    Text("選擇", color = Color.White, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun DoctorSpecialtyContent(doctor: Doctor) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 28.dp)
            .padding(bottom = 42.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = Icons.Default.ThumbUp,
                contentDescription = null,
                tint = Color(0xFFE67E22),
                modifier = Modifier.size(28.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                text = "${doctor.name} 專長",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold
            )
        }

        HorizontalDivider(modifier = Modifier.padding(vertical = 16.dp), color = Color(0xFFE0E6E6))

        doctor.specialties.forEach { specialty ->
            Text(
                text = specialty,
                fontSize = 17.sp,
                lineHeight = 26.sp,
                color = Color(0xFF3C4A4A),
                modifier = Modifier.padding(vertical = 4.dp)
            )
        }
    }
}
