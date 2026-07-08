package com.example.medicalaiguidance.navigation

import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.example.medicalaiguidance.screen.ChatScreen
import com.example.medicalaiguidance.screen.ConfirmNeedScreen
import com.example.medicalaiguidance.screen.DoctorSelectionScreen
import com.example.medicalaiguidance.screen.HistoryScreen
import com.example.medicalaiguidance.screen.HomeScreen
import com.example.medicalaiguidance.screen.MockScheduleTestScreen
import com.example.medicalaiguidance.viewmodel.HistoryViewModel

object Route {
    const val HOME = "home"
    const val CHAT = "chat"
    const val CHAT_HISTORY = "chat/{historyId}"
    const val SELECT_DOCTOR = "select_doctor"
    const val CONFIRM_NEED = "confirm_need"
    const val HISTORY = "history"
    const val MOCK_SCHEDULE_TEST = "mock_schedule_test"

    fun chatHistory(historyId: String): String = "chat/$historyId"
}

@Composable
fun NavGraph(navController: NavHostController) {
    NavHost(
        navController = navController,
        startDestination = Route.HOME
    ) {
        composable(Route.HOME) {
            HomeScreen(navController = navController)
        }

        composable(Route.CHAT) {
            ChatScreen(navController = navController, startNew = true)
        }

        composable(
            route = Route.CHAT_HISTORY,
            arguments = listOf(navArgument("historyId") { type = NavType.StringType })
        ) { backStackEntry ->
            ChatScreen(
                navController = navController,
                historyId = backStackEntry.arguments?.getString("historyId")
            )
        }

        composable(Route.SELECT_DOCTOR) {
            DoctorSelectionScreen(navController)
        }

        composable(Route.CONFIRM_NEED) {
            ConfirmNeedScreen(navController)
        }

        composable(Route.HISTORY) {
            val historyViewModel: HistoryViewModel = viewModel()
            HistoryScreen(navController = navController, viewModel = historyViewModel)
        }

        composable(Route.MOCK_SCHEDULE_TEST) {
            MockScheduleTestScreen(navController = navController)
        }
    }
}
