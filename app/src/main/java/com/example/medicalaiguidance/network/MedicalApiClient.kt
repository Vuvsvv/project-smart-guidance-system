package com.example.medicalaiguidance.network

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStream
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL

class MedicalApiClient(
    private val baseUrl: String = DEFAULT_BASE_URL
) {
    suspend fun chat(request: ChatRequest): TriageResultDto =
        post("/chat", request.toJson(), ::parseTriageResult)

    suspend fun recommend(request: RecommendRequest): RecommendationResultDto =
        post("/recommend", request.toJson(), ::parseRecommendationResult)

    suspend fun generateScript(request: ScriptRequest): ScriptResponseDto =
        post("/generate_script", request.toJson(), ::parseScriptResponse)

    private suspend fun <T> post(
        path: String,
        body: String,
        parser: (String) -> T
    ): T = withContext(Dispatchers.IO) {
        val endpoint = baseUrl.trimEnd('/') + path
        Log.d(TAG, "POST $endpoint")

        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            doInput = true
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", "application/json")
        }

        try {
            connection.outputStream.use { output ->
                output.write(body.toByteArray(Charsets.UTF_8))
            }

            val statusCode = connection.responseCode
            val responseBody = readBody(
                if (statusCode in 200..299) connection.inputStream else connection.errorStream
            )
            Log.d(TAG, "HTTP $statusCode $path")

            if (statusCode !in 200..299) {
                throw MedicalApiException("後端回應錯誤 HTTP $statusCode：${extractErrorMessage(responseBody)}")
            }

            parser(responseBody)
        } catch (error: MedicalApiException) {
            Log.e(TAG, "API error on $path: ${error.message}")
            throw error
        } catch (error: SocketTimeoutException) {
            Log.e(TAG, "Request timeout on $path", error)
            throw MedicalApiException("AI 回覆時間較長，請稍後再試。若第一次開啟 Render 服務，可能需要等待冷啟動。", error)
        } catch (error: IOException) {
            Log.e(TAG, "Network error on $path", error)
            throw MedicalApiException("無法連線後端，請確認手機網路可連到：$baseUrl", error)
        } catch (error: Exception) {
            Log.e(TAG, "Request error on $path", error)
            throw MedicalApiException("請求後端時發生錯誤：${error.message ?: "未知錯誤"}", error)
        } finally {
            connection.disconnect()
        }
    }

    private fun readBody(stream: InputStream?): String {
        if (stream == null) return ""
        return BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { reader ->
            reader.readText()
        }
    }

    private fun extractErrorMessage(responseBody: String): String {
        if (responseBody.isBlank()) return "沒有錯誤內容"
        return runCatching {
            JSONObject(responseBody).optString("detail", responseBody)
        }.getOrDefault(responseBody)
    }

    companion object {
        private const val TAG = "MedicalApiClient"
        private const val CONNECT_TIMEOUT_MS = 15_000
        private const val READ_TIMEOUT_MS = 60_000
        const val DEFAULT_BASE_URL = "https://android-medical-myself.onrender.com"
    }
}

class MedicalApiException(
    message: String,
    cause: Throwable? = null
) : Exception(message, cause)
