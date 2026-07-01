package com.example.medicalaiguidance.util

import android.media.AudioAttributes
import android.media.MediaPlayer
import android.util.Base64
import java.io.File
import java.io.FileOutputStream

class AudioPlayer {
    private var player: MediaPlayer? = null
    private var currentFile: File? = null

    fun playBase64(base64Audio: String, cacheDir: File, audioFormat: String = "wav", onDone: () -> Unit = {}) {
        if (base64Audio.isBlank()) {
            onDone()
            return
        }

        val bytes = Base64.decode(base64Audio, Base64.DEFAULT)
        val extension = audioFormat.ifBlank { "wav" }
        val audioFile = File(cacheDir, "tts_${System.currentTimeMillis()}.$extension")
        FileOutputStream(audioFile).use { it.write(bytes) }

        release()
        currentFile = audioFile
        player = MediaPlayer().apply {
            setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            setDataSource(audioFile.absolutePath)
            setOnCompletionListener {
                release()
                onDone()
            }
            setOnErrorListener { _, _, _ ->
                release()
                onDone()
                true
            }
            prepare()
            start()
        }
    }

    fun release() {
        player?.release()
        player = null
        currentFile?.delete()
        currentFile = null
    }
}
