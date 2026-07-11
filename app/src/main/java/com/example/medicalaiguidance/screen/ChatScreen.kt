package com.example.medicalaiguidance.screen

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
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
import androidx.compose.foundation.layout.offset
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
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
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
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
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
import androidx.core.content.ContextCompat
import com.example.medicalaiguidance.R
import com.example.medicalaiguidance.model.MessageSender
import com.example.medicalaiguidance.navigation.Route
import com.example.medicalaiguidance.util.AudioPlayer
import com.example.medicalaiguidance.viewmodel.ChatViewModel
import java.util.Locale
import kotlinx.coroutines.delay

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
    val hintGray = Color(0xFF8FA3A6)
    val micBgColor = Color(0xFFE5F2F2)

    val messages by viewModel.messages.collectAsState()
    val inputText by viewModel.inputText.collectAsState()
    val isAiThinking by viewModel.isAiThinking.collectAsState()
    val isListening by viewModel.isListening.collectAsState()
    val showDecisionButtons by viewModel.showDecisionButtons.collectAsState()
    val speakingMessageId by viewModel.speakingMessageId.collectAsState()
    var selectedLanguage by remember { mutableStateOf("國語") }
    var isInputFocused by remember { mutableStateOf(false) }
    val canSendMessage = inputText.isNotBlank() && !isAiThinking

    val listState = rememberLazyListState()
    val context = LocalContext.current
    val audioPlayer = remember { AudioPlayer() }
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
    val audioPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            viewModel.startTaiwaneseRecording()
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
    val isTaiwaneseMode = selectedLanguage == "台語"
    val currentVoiceLang = if (isTaiwaneseMode) "taiwanese" else "chinese"
    val handleMicClick = {
        if (isTaiwaneseMode) {
            keyboardController?.hide()
            if (isListening) {
                viewModel.stopTaiwaneseRecordingAndSend(
                    audioPlayer = audioPlayer,
                    cacheDir = context.cacheDir
                ) {
                    navController.navigate(Route.SELECT_DOCTOR)
                }
            } else if (!isAiThinking) {
                val hasPermission = ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.RECORD_AUDIO
                ) == PackageManager.PERMISSION_GRANTED

                if (hasPermission) {
                    viewModel.startTaiwaneseRecording()
                } else {
                    audioPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                }
            }
        } else {
            launchVoiceInput()
        }
    }

    DisposableEffect(Unit) {
        onDispose { audioPlayer.release() }
    }

    LaunchedEffect(historyId, startNew) {
        when {
            historyId != null -> viewModel.openHistory(historyId)
            startNew -> viewModel.startNewConversation()
        }
    }

    LaunchedEffect(
        messages.lastOrNull()?.id,
        isAiThinking,
        showDecisionButtons,
        inputText,
        isInputFocused
    ) {
        if (messages.isNotEmpty()) {
            val conversationStartIndex = messages.indexOfLast { it.sender == MessageSender.USER }
                .takeIf { it >= 0 }
                ?: messages.lastIndex
            delay(80)
            listState.animateScrollToItem(conversationStartIndex)
            if (isInputFocused || isAiThinking || showDecisionButtons) {
                delay(220)
                listState.animateScrollToItem(conversationStartIndex)
            }
        }
    }

    val performSendMessage = {
        if (canSendMessage) {
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
        // ---- Message list (bottom layer) ----
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.TopCenter
        ) {
            if (messages.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 150.dp),
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
                contentPadding = PaddingValues(
                    start = 18.dp,
                    end = 18.dp,
                    top = 16.dp,
                    bottom = 152.dp
                ),
                verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.Bottom)
            ) {
                items(messages, key = { it.id }) { msg ->
                    val isUser = msg.sender == MessageSender.USER
                    val isLastMessage = msg.id == messages.lastOrNull()?.id

                    Column(modifier = Modifier.fillMaxWidth()) {
                        RealBubbleItem(
                            messageContent = msg.content,
                            isUser = isUser,
                            primaryDark = primaryDark,
                            isSpeaking = speakingMessageId == msg.id,
                            onSpeakClicked = {
                                viewModel.speakMessage(
                                    message = msg,
                                    audioPlayer = audioPlayer,
                                    cacheDir = context.cacheDir,
                                    lang = currentVoiceLang
                                )
                            }
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
                        AiThinkingBubble(primaryDark = primaryDark)
                    }
                }

                item(key = "chat_bottom_anchor") {
                    Spacer(modifier = Modifier.height(1.dp))
                }
            }
        }

        // ----頂部遮罩層 漸進式變淡 Header (floating overlay, fades to transparent) ----
        Row(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .fillMaxWidth()
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            Color(0xFFF5F9F9).copy(alpha = 0.95f),
                            Color(0xFFEBF3F2).copy(alpha = 0.75f),
                            Color(0xFFEBF3F2).copy(alpha = 0.35f),
                            Color(0xFFF8FAFA).copy(alpha = 0f)
                        )
                    )
                )
                .statusBarsPadding()
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

        // ---- Input bar (floating overlay at bottom) ----
        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(start = 20.dp, end = 20.dp, bottom = 16.dp)
                .heightIn(min = 68.dp, max = 112.dp)
                .shadow(elevation = 8.dp, shape = RoundedCornerShape(34.dp))
                .background(Color.White, shape = RoundedCornerShape(34.dp))
                .padding(start = 8.dp, end = 20.dp, top = 4.dp, bottom = 4.dp),
            contentAlignment = Alignment.CenterStart
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(52.dp)
                        .background(
                            color = if (isListening) Color(0xFFE74C3C) else micBgColor,
                            shape = CircleShape
                        )
                        .clickable { handleMicClick() },
                    contentAlignment = Alignment.Center
                ) {
                    if (isListening) {
                        Icon(
                            imageVector = Icons.Default.Stop,
                            contentDescription = "停止錄音",
                            tint = Color.White,
                            modifier = Modifier.size(26.dp)
                        )
                    } else {
                        Icon(
                            painter = painterResource(id = R.drawable.ic_mic),
                            contentDescription = "語音輸入",
                            tint = primaryDark,
                            modifier = Modifier.size(26.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.width(14.dp))

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .padding(vertical = 6.dp)
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
                        modifier = Modifier
                            .fillMaxWidth()
                            .onFocusChanged { isInputFocused = it.isFocused }
                    )
                }

                Spacer(modifier = Modifier.width(12.dp))

                Icon(
                    painter = painterResource(id = R.drawable.ic_send),
                    contentDescription = "送出",
                    tint = if (canSendMessage) primaryDark else Color.LightGray,
                    modifier = Modifier
                        .size(34.dp)
                        .clickable(enabled = canSendMessage) { performSendMessage() }
                )
            }
        }
    }
}

@Composable
fun AiThinkingBubble(primaryDark: Color) {
    val transition = rememberInfiniteTransition(label = "aiThinkingDots")
    val dotOffsets = List(3) { index ->
        transition.animateFloat(
            initialValue = 0f,
            targetValue = -6f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 420, delayMillis = index * 130),
                repeatMode = RepeatMode.Reverse
            ),
            label = "aiThinkingDot$index"
        )
    }

    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier
            .shadow(
                elevation = 3.dp,
                shape = RoundedCornerShape(
                    topStart = 24.dp,
                    topEnd = 24.dp,
                    bottomStart = 4.dp,
                    bottomEnd = 24.dp
                )
            )
            .background(
                Color.White,
                shape = RoundedCornerShape(
                    topStart = 24.dp,
                    topEnd = 24.dp,
                    bottomStart = 4.dp,
                    bottomEnd = 24.dp
                )
            )
            .padding(horizontal = 18.dp, vertical = 14.dp)
    ) {

        dotOffsets.forEach { offset ->
            Text(
                text = "•",
                color = primaryDark,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.offset(y = offset.value.dp)
            )
        }
        /*Text(
            text = "正在分析中請稍後",
            color = primaryDark,
            fontSize = 16.sp,
            fontWeight = FontWeight.Medium
        )*/2
    }
}

@Composable
fun RealBubbleItem(
    messageContent: String,
    isUser: Boolean,
    primaryDark: Color,
    isSpeaking: Boolean = false,
    onSpeakClicked: () -> Unit = {}
) {
    val warningOrange = Color(0xFFE6A23C)
    val inactiveIcon = Color(0xFF8FA3A6)
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
                        modifier = Modifier.clickable { onSpeakClicked() },
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.VolumeUp,
                            contentDescription = "播放語音",
                            tint = if (isSpeaking) primaryDark else inactiveIcon,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "播放",
                            color = if (isSpeaking) primaryDark else inactiveIcon,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Normal
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
    val itemWidth = 64.dp
    val indicatorOffset by animateDpAsState(
        targetValue = if (selectedLanguage == "台語") itemWidth else 0.dp,
        animationSpec = tween(durationMillis = 260),
        label = "languageToggleOffset"
    )

    Box(
        modifier = Modifier
            .height(58.dp)
            .width(itemWidth * 2 + 12.dp)
            .shadow(elevation = 4.dp, shape = RoundedCornerShape(30.dp))
            .background(Color.White, shape = RoundedCornerShape(30.dp))
            .padding(6.dp)
    ) {
        Box(
            modifier = Modifier
                .offset(x = indicatorOffset)
                .height(46.dp)
                .width(itemWidth)
                .background(selectedColor, RoundedCornerShape(24.dp))
        )

        Row(verticalAlignment = Alignment.CenterVertically) {
            LanguageToggleItem(
                text = "國語",
                primaryDark = primaryDark,
                onClick = { onLanguageSelected("國語") }
            )
            LanguageToggleItem(
                text = "台語",
                primaryDark = primaryDark,
                onClick = { onLanguageSelected("台語") }
            )
        }
    }
}

@Composable
fun LanguageToggleItem(
    text: String,
    primaryDark: Color,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .height(46.dp)
            .width(64.dp)
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

