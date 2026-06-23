package com.example.medicalaiguidance.screen

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
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
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import com.example.medicalaiguidance.model.MessageSender
import com.example.medicalaiguidance.navigation.Route
import com.example.medicalaiguidance.viewmodel.ChatViewModel
import java.util.Locale

@Composable
fun ChatScreen(
    navController: NavHostController,
    historyId: String? = null,
    startNew: Boolean = false,
    viewModel: ChatViewModel = viewModel()
) {
    val bgGradient = Brush.verticalGradient(
        colors = listOf(Color(0xFFF5F9F9), Color(0xFFE8F2F1), Color(0xFFF8FAFA))
    )
    val primaryDark = Color(0xFF2F6F73)
    val hintGray = Color(0xFF7B8588)
    val micBgColor = Color(0xFFE5F2F2)

    val messages by viewModel.messages.collectAsState()
    val inputText by viewModel.inputText.collectAsState()
    val isAiThinking by viewModel.isAiThinking.collectAsState()
    val isListening by viewModel.isListening.collectAsState()
    val showDecisionButtons by viewModel.showDecisionButtons.collectAsState()
    var selectedLanguage by remember { mutableStateOf("國語") }

    val listState = rememberLazyListState()
    val keyboardController = LocalSoftwareKeyboardController.current
    val speechLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        viewModel.setListening(false)
        if (result.resultCode == Activity.RESULT_OK) {
            val transcript = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
                .orEmpty()
            viewModel.submitVoiceInput(transcript) {
                navController.navigate(Route.SELECT_DOCTOR)
            }
        }
    }

    val launchVoiceInput = {
        if (!isAiThinking) {
            keyboardController?.hide()
            viewModel.setListening(true)
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.TAIWAN.toLanguageTag())
                putExtra(RecognizerIntent.EXTRA_PROMPT, "請說出你的症狀或想掛號的需求")
            }
            try {
                speechLauncher.launch(intent)
            } catch (_: ActivityNotFoundException) {
                viewModel.setListening(false)
                viewModel.onInputTextChanged("這台手機沒有可用的語音輸入服務")
            }
        }
    }

    LaunchedEffect(historyId, startNew) {
        when {
            historyId != null -> viewModel.openHistory(historyId)
            startNew -> viewModel.startNewConversation()
        }
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    val performSendMessage = {
        if (inputText.isNotBlank() && !isAiThinking) {
            keyboardController?.hide()
            viewModel.sendMessage {
                navController.navigate(Route.SELECT_DOCTOR)
            }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(bgGradient)
            .imePadding()
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 22.dp, vertical = 16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .shadow(elevation = 4.dp, shape = RoundedCornerShape(16.dp))
                        .background(Color.White, shape = RoundedCornerShape(16.dp))
                        .clickable { navController.popBackStack() },
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "返回",
                        tint = primaryDark,
                        modifier = Modifier.size(22.dp)
                    )
                }

                Spacer(modifier = Modifier.weight(1f))

                LanguageToggle(
                    selectedLanguage = selectedLanguage,
                    onLanguageSelected = { selectedLanguage = it },
                    primaryDark = primaryDark,
                    selectedColor = micBgColor
                )
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.TopCenter
            ) {
                if (messages.isEmpty()) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 64.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "不舒服嗎？請告訴我",
                            color = primaryDark,
                            fontSize = 27.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 18.dp, vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.Bottom)
                ) {
                    items(messages, key = { it.id }) { msg ->
                        val isUser = msg.sender == MessageSender.USER
                        val isLastMessage = msg.id == messages.lastOrNull()?.id

                        Column(modifier = Modifier.fillMaxWidth()) {
                            RealBubbleItem(
                                messageContent = msg.content,
                                isUser = isUser,
                                primaryDark = primaryDark
                            )

                            if (showDecisionButtons && !isUser && isLastMessage) {
                                AnimatedVisibility(
                                    visible = true,
                                    enter = fadeIn() + slideInVertically(initialOffsetY = { it / 2 })
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(top = 12.dp),
                                        horizontalArrangement = Arrangement.spacedBy(14.dp)
                                    ) {
                                        ChatActionButton(
                                            text = "看推薦醫生",
                                            containerColor = primaryDark,
                                            contentColor = Color.White,
                                            modifier = Modifier.weight(1f),
                                            onClick = {
                                                viewModel.chooseRecommendation()
                                                navController.navigate(Route.SELECT_DOCTOR)
                                            }
                                        )
                                        ChatActionButton(
                                            text = "我想修改",
                                            containerColor = Color(0xFFD5E5E5),
                                            contentColor = primaryDark,
                                            modifier = Modifier.weight(1f),
                                            onClick = { viewModel.continueEditing() }
                                        )
                                    }
                                }
                            }
                        }
                    }

                    if (isAiThinking) {
                        item {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier
                                    .background(Color.White, shape = RoundedCornerShape(18.dp))
                                    .padding(horizontal = 16.dp, vertical = 10.dp)
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(16.dp),
                                    color = primaryDark,
                                    strokeWidth = 2.dp
                                )
                                Spacer(modifier = Modifier.width(10.dp))
                                Text(
                                    text = "AI 正在分析...",
                                    color = primaryDark,
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        }
                    }
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(start = 20.dp, end = 20.dp, bottom = 20.dp)
                    .heightIn(min = 78.dp, max = 126.dp)
                    .shadow(elevation = 10.dp, shape = RoundedCornerShape(40.dp))
                    .background(Color.White, shape = RoundedCornerShape(40.dp))
                    .padding(start = 8.dp, end = 24.dp, top = 6.dp, bottom = 6.dp),
                contentAlignment = Alignment.CenterStart
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(58.dp)
                            .background(
                                color = if (isListening) Color(0xFFE74C3C) else micBgColor,
                                shape = CircleShape
                            )
                            .clickable { launchVoiceInput() },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = if (isListening) Icons.Default.Stop else Icons.Default.Mic,
                            contentDescription = "語音輸入",
                            tint = if (isListening) Color.White else primaryDark,
                            modifier = Modifier.size(28.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(18.dp))

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .padding(vertical = 8.dp)
                    ) {
                        if (inputText.isEmpty()) {
                            Text(
                                text = if (isListening) "正在聆聽..." else "點我詢問",
                                color = hintGray,
                                fontSize = 18.sp
                            )
                        }
                        BasicTextField(
                            value = inputText,
                            onValueChange = { viewModel.onInputTextChanged(it) },
                            maxLines = 3,
                            textStyle = TextStyle(color = primaryDark, fontSize = 18.sp),
                            cursorBrush = SolidColor(primaryDark),
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                            keyboardActions = KeyboardActions(onSearch = { performSendMessage() }),
                            modifier = Modifier.fillMaxWidth()
                        )
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.Send,
                        contentDescription = "送出",
                        tint = if (isAiThinking) Color.LightGray else primaryDark,
                        modifier = Modifier
                            .size(34.dp)
                            .clickable { performSendMessage() }
                    )
                }
            }
        }
    }
}

@Composable
fun RealBubbleItem(
    messageContent: String,
    isUser: Boolean,
    primaryDark: Color
) {
    val warningOrange = Color(0xFFE6A23C)
    val inactiveIcon = Color(0xFFCCCCCC)
    val bubbleShape = if (isUser) {
        RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp, bottomStart = 24.dp, bottomEnd = 4.dp)
    } else {
        RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp, bottomStart = 4.dp, bottomEnd = 24.dp)
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        if (isUser) {
            Box(
                modifier = Modifier
                    .widthIn(max = 280.dp)
                    .shadow(elevation = 1.dp, shape = bubbleShape)
                    .background(primaryDark, shape = bubbleShape)
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Text(
                    text = messageContent,
                    color = Color.White,
                    fontSize = 16.sp,
                    lineHeight = 24.sp
                )
            }
            return@Column
        }

        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .padding(start = 4.dp, bottom = 6.dp)
                .background(Color(0xFFFDF6EC), shape = RoundedCornerShape(6.dp))
                .padding(horizontal = 8.dp, vertical = 4.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .background(warningOrange, shape = CircleShape)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = "本資訊僅供參考！若有緊急症狀請立即就醫",
                color = warningOrange,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold
            )
        }

        Box(
            modifier = Modifier
                .widthIn(max = 280.dp)
                .shadow(elevation = 3.dp, shape = bubbleShape)
                .background(Color.White, shape = bubbleShape)
                .clip(bubbleShape)
        ) {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = messageContent.withBoldDepartment(),
                    color = primaryDark,
                    fontSize = 16.sp,
                    lineHeight = 24.sp,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)
                )

                Box(
                    modifier = Modifier
                        .padding(horizontal = 16.dp)
                        .fillMaxWidth()
                        .height(1.dp)
                        .background(Color(0xFFEEEEEE))
                )

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(
                        modifier = Modifier.clickable { },
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.VolumeUp,
                            contentDescription = "播放語音",
                            tint = inactiveIcon,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "播放",
                            color = inactiveIcon,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Normal
                        )
                    }

                    Spacer(modifier = Modifier.weight(1f))

                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.ThumbUp,
                            contentDescription = "有幫助",
                            tint = inactiveIcon,
                            modifier = Modifier
                                .size(22.dp)
                                .clickable { }
                        )
                        Icon(
                            imageVector = Icons.Default.ThumbDown,
                            contentDescription = "沒有幫助",
                            tint = inactiveIcon,
                            modifier = Modifier
                                .size(22.dp)
                                .clickable { }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun LanguageToggle(
    selectedLanguage: String,
    onLanguageSelected: (String) -> Unit,
    primaryDark: Color,
    selectedColor: Color
) {
    Row(
        modifier = Modifier
            .height(58.dp)
            .shadow(elevation = 4.dp, shape = RoundedCornerShape(30.dp))
            .background(Color.White, shape = RoundedCornerShape(30.dp))
            .padding(6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        LanguageToggleItem(
            text = "國語",
            selected = selectedLanguage == "國語",
            primaryDark = primaryDark,
            selectedColor = selectedColor,
            onClick = { onLanguageSelected("國語") }
        )
        LanguageToggleItem(
            text = "台語",
            selected = selectedLanguage == "台語",
            primaryDark = primaryDark,
            selectedColor = selectedColor,
            onClick = { onLanguageSelected("台語") }
        )
    }
}

@Composable
fun LanguageToggleItem(
    text: String,
    selected: Boolean,
    primaryDark: Color,
    selectedColor: Color,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .height(46.dp)
            .width(64.dp)
            .background(
                color = if (selected) selectedColor else Color.Transparent,
                shape = RoundedCornerShape(24.dp)
            )
            .clickable { onClick() },
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = primaryDark,
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold
        )
    }
}

private fun String.withBoldDepartment() = buildAnnotatedString {
    val target = "檢傷結果"
    val startIndex = indexOf(target)
    if (startIndex == -1) {
        append(this@withBoldDepartment)
        return@buildAnnotatedString
    }

    append(substring(0, startIndex))
    withStyle(SpanStyle(fontWeight = FontWeight.ExtraBold)) {
        append(target)
    }
    append(substring(startIndex + target.length))
}

@Composable
fun ChatActionButton(
    text: String,
    containerColor: Color,
    contentColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .height(54.dp)
            .shadow(elevation = 4.dp, shape = RoundedCornerShape(18.dp))
            .background(containerColor, shape = RoundedCornerShape(18.dp))
            .clickable { onClick() },
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = contentColor,
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold
        )
    }
}
