package com.insta360.kmpsdk.demo.util

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.view.PixelCopy
import android.view.View
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import kotlin.coroutines.resume

/**
 * 把预览画面截成 JPEG，经 adb reverse 发到电脑 127.0.0.1:8080。
 * 电脑需先执行：adb reverse tcp:8080 tcp:8080
 */
class PcDetectBridge {
    private val mainHandler = Handler(Looper.getMainLooper())
    private var job: Job? = null

    val running: Boolean
        get() = job?.isActive == true

    fun start(
        scope: CoroutineScope,
        activity: Activity,
        previewView: () -> View?,
        onStatus: (Status) -> Unit,
    ) {
        stop()
        job =
            scope.launch(Dispatchers.IO) {
                if (!ping()) {
                    onStatus(Status.Unreachable)
                    return@launch
                }
                onStatus(Status.Sending)
                while (isActive) {
                    val jpeg = captureJpeg(activity, previewView)
                    if (jpeg != null) {
                        runCatching { postFrame(jpeg) }
                            .onFailure { Timber.w(it, "send frame failed") }
                    }
                    delay(FRAME_INTERVAL_MS)
                }
            }
    }

    fun stop() {
        job?.cancel()
        job = null
    }

    private suspend fun captureJpeg(
        activity: Activity,
        previewView: () -> View?,
    ): ByteArray? {
        val bitmap =
            suspendCancellableCoroutine<Bitmap?> { cont ->
                mainHandler.post {
                    val view = previewView()
                    val window = activity.window
                    if (view == null || window == null || view.width <= 2 || view.height <= 2) {
                        if (cont.isActive) cont.resume(null)
                        return@post
                    }
                    val loc = IntArray(2)
                    view.getLocationInWindow(loc)
                    val src = Rect(loc[0], loc[1], loc[0] + view.width, loc[1] + view.height)
                    val bmp = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
                    try {
                        PixelCopy.request(window, src, bmp, { result ->
                            if (!cont.isActive) {
                                bmp.recycle()
                                return@request
                            }
                            if (result == PixelCopy.SUCCESS) {
                                cont.resume(bmp)
                            } else {
                                bmp.recycle()
                                Timber.w("PixelCopy failed: %s", result)
                                cont.resume(null)
                            }
                        }, mainHandler)
                    } catch (t: Throwable) {
                        bmp.recycle()
                        Timber.w(t, "PixelCopy request failed")
                        if (cont.isActive) cont.resume(null)
                    }
                }
            } ?: return null
        return try {
            withContext(Dispatchers.Default) { encodeJpeg(bitmap) }
        } finally {
            if (!bitmap.isRecycled) bitmap.recycle()
        }
    }

    private fun encodeJpeg(src: Bitmap): ByteArray {
        val scaled = scaleDown(src, MAX_SIDE)
        return try {
            ByteArrayOutputStream().use { out ->
                scaled.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out)
                out.toByteArray()
            }
        } finally {
            if (scaled !== src && !scaled.isRecycled) scaled.recycle()
        }
    }

    private fun scaleDown(
        src: Bitmap,
        maxSide: Int,
    ): Bitmap {
        val longSide = maxOf(src.width, src.height)
        if (longSide <= maxSide) return src
        val scale = maxSide.toFloat() / longSide
        val w = (src.width * scale).toInt().coerceAtLeast(1)
        val h = (src.height * scale).toInt().coerceAtLeast(1)
        return Bitmap.createScaledBitmap(src, w, h, true)
    }

    private fun ping(): Boolean =
        try {
            val conn = open("GET", "/health")
            conn.connectTimeout = 800
            conn.readTimeout = 800
            conn.connect()
            val ok = conn.responseCode in 200..299
            conn.disconnect()
            ok
        } catch (t: Throwable) {
            Timber.w(t, "pc detect ping failed")
            false
        }

    private fun postFrame(jpeg: ByteArray) {
        val conn = open("POST", "/frame")
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "image/jpeg")
        conn.setRequestProperty("Content-Length", jpeg.size.toString())
        conn.connectTimeout = 800
        conn.readTimeout = 800
        conn.outputStream.use { it.write(jpeg) }
        conn.inputStream.use { it.readBytes() }
        conn.disconnect()
    }

    private fun open(
        method: String,
        path: String,
    ): HttpURLConnection {
        val conn = URL(BASE_URL + path).openConnection() as HttpURLConnection
        conn.requestMethod = method
        conn.useCaches = false
        return conn
    }

    enum class Status { Sending, Unreachable }

    companion object {
        const val BASE_URL = "http://127.0.0.1:8080"
        private const val FRAME_INTERVAL_MS = 125L
        private const val MAX_SIDE = 640
        private const val JPEG_QUALITY = 70
    }
}
