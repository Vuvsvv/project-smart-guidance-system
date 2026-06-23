package com.example.medicalaiguidance

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.navigation.compose.rememberNavController
import com.example.medicalaiguidance.navigation.NavGraph
import com.example.medicalaiguidance.repository.MedicalRepository

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        MedicalRepository.initialize(applicationContext)
        enableEdgeToEdge()

        setContent {
            val navController = rememberNavController()
            NavGraph(navController = navController)
        }
    }
}
