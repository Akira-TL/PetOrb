package com.petorb.bridge

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class EncodedStreamBridge(
    private val url: String,
    private val onStatus: (String) -> Unit,
    private val onError: (Throwable) -> Unit,
) {
    private val client = OkHttpClient.Builder()
        .pingInterval(10, TimeUnit.SECONDS)
        .build()

    @Volatile
    private var socket: WebSocket? = null

    @Volatile
    private var opened = false

    @Volatile
    private var metadata: JSONObject? = null

    @Volatile
    private var metadataSent = false

    fun connect() {
        if (socket != null) return
        val request = Request.Builder().url(url).build()
        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                opened = true
                onStatus("USB/WebSocket 已连接电脑")
                sendMetadataIfReady(webSocket)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                opened = false
                onStatus("USB/WebSocket 正在关闭")
                webSocket.close(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                opened = false
                socket = null
                onStatus("USB/WebSocket 已断开")
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                opened = false
                socket = null
                onError(t)
            }
        })
    }

    fun setStreamMetadata(codec: String, width: Int, height: Int, fps: Int) {
        metadata = JSONObject().apply {
            put("type", "stream_config")
            put("codec", codec)
            put("width", width)
            put("height", height)
            put("fps", fps)
        }
        metadataSent = false
        socket?.takeIf { opened }?.let(::sendMetadataIfReady)
    }

    fun sendEncodedVideo(data: ByteArray): Boolean {
        val webSocket = socket ?: return false
        if (!opened || !metadataSent) return false
        if (webSocket.queueSize() > MAX_QUEUED_BYTES) return false
        return webSocket.send(data.toByteString())
    }

    fun close() {
        opened = false
        metadataSent = false
        socket?.close(1000, "camera stream stopped")
        socket = null
        client.dispatcher.executorService.shutdown()
        client.connectionPool.evictAll()
    }

    private fun sendMetadataIfReady(webSocket: WebSocket) {
        val current = metadata ?: return
        if (webSocket.send(current.toString())) {
            metadataSent = true
        }
    }

    companion object {
        private const val MAX_QUEUED_BYTES = 4L * 1024L * 1024L
    }
}
