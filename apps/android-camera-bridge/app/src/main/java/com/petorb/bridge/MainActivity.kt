package com.petorb.bridge

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var cameraController: Go3sCameraController
    private lateinit var streamUrlInput: EditText
    private lateinit var cameraStatus: TextView
    private lateinit var bridgeStatus: TextView
    private lateinit var lastError: TextView
    private lateinit var connectButton: Button
    private lateinit var startStreamButton: Button
    private lateinit var stopStreamButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cameraController = Go3sCameraController(
            context = this,
            onCameraStatus = { message -> runOnUiThread { cameraStatus.text = "相机：$message" } },
            onBridgeStatus = { message -> runOnUiThread { bridgeStatus.text = "电脑桥：$message" } },
            onConnected = {
                runOnUiThread {
                    connectButton.isEnabled = false
                    startStreamButton.isEnabled = true
                    stopStreamButton.isEnabled = false
                    lastError.text = "最近错误：无"
                }
            },
            onStreamingChanged = { streaming ->
                runOnUiThread {
                    startStreamButton.isEnabled = !streaming
                    stopStreamButton.isEnabled = streaming
                }
            },
            onError = { error ->
                runOnUiThread {
                    lastError.text = "最近错误：${error.message ?: error.javaClass.simpleName}"
                }
            },
        )
        setContentView(buildUi())
    }

    private fun buildUi(): ScrollView {
        val density = resources.displayMetrics.density
        fun dp(value: Int) = (value * density).toInt()

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(24), dp(24), dp(24))
        }

        container.addView(TextView(this).apply {
            text = "PetOrb Camera Bridge"
            textSize = 26f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        })
        container.addView(TextView(this).apply {
            text = "GO 3S H.264/H.265 → USB/ADB reverse → PetOrb PC"
            textSize = 14f
            setPadding(0, dp(6), 0, dp(24))
        })

        cameraStatus = statusText("相机：未连接")
        bridgeStatus = statusText("电脑桥：未连接")
        lastError = statusText("最近错误：无")
        listOf(cameraStatus, bridgeStatus, lastError).forEach(container::addView)

        connectButton = Button(this).apply {
            text = "扫描并连接 GO 3S"
            setOnClickListener { requestCameraPermissionsAndConnect() }
        }
        container.addView(connectButton)

        container.addView(TextView(this).apply {
            text = "电脑 WebSocket 地址"
            setPadding(0, dp(20), 0, dp(6))
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        })
        streamUrlInput = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
            setText(
                getSharedPreferences(PREFS, MODE_PRIVATE)
                    .getString(KEY_STREAM_URL, DEFAULT_STREAM_URL)
            )
        }
        container.addView(streamUrlInput, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

        startStreamButton = Button(this).apply {
            text = "开始实时桥接"
            isEnabled = false
            setOnClickListener {
                val url = streamUrlInput.text.toString().trim().ifBlank { DEFAULT_STREAM_URL }
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_STREAM_URL, url).apply()
                lastError.text = "最近错误：无"
                cameraController.startStreaming(url)
            }
        }
        container.addView(startStreamButton)

        stopStreamButton = Button(this).apply {
            text = "停止实时桥接"
            isEnabled = false
            setOnClickListener { cameraController.stopStreaming() }
        }
        container.addView(stopStreamButton)

        container.addView(TextView(this).apply {
            text = "现场先在电脑执行 adb reverse tcp:8010 tcp:8010。手机 Wi-Fi 全程保持连接 GO 3S；编码 PreviewStream 不在手机解码，直接经 USB 发送到电脑，由 FFmpeg 解码为 30 FPS，电脑每 3 帧抽 1 帧做约 10 FPS 本地 AI。"
            textSize = 13f
            setPadding(0, dp(20), 0, 0)
        })

        return ScrollView(this).apply { addView(container) }
    }

    private fun statusText(initial: String) = TextView(this).apply {
        text = initial
        textSize = 17f
        setPadding(0, 10, 0, 10)
    }

    private fun requestCameraPermissionsAndConnect() {
        val missing = requiredRuntimePermissions().filter {
            checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) startCameraConnection()
        else requestPermissions(missing.toTypedArray(), CAMERA_PERMISSION_REQUEST)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != CAMERA_PERMISSION_REQUEST) return
        if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            startCameraConnection()
        } else {
            lastError.text = "最近错误：需要蓝牙/Wi-Fi 权限才能连接 GO 3S"
        }
    }

    private fun startCameraConnection() {
        connectButton.isEnabled = false
        startStreamButton.isEnabled = false
        lastError.text = "最近错误：无"
        cameraController.scanAndConnect()
    }

    private fun requiredRuntimePermissions(): List<String> = buildList {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            add(Manifest.permission.BLUETOOTH_SCAN)
            add(Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            add(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(Manifest.permission.NEARBY_WIFI_DEVICES)
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            add(Manifest.permission.ACCESS_FINE_LOCATION)
        }
    }.distinct()

    override fun onDestroy() {
        cameraController.release()
        super.onDestroy()
    }

    companion object {
        private const val PREFS = "petorb-bridge"
        private const val KEY_STREAM_URL = "stream-url"
        private const val DEFAULT_STREAM_URL = "ws://127.0.0.1:8010/ws/camera/source"
        private const val CAMERA_PERMISSION_REQUEST = 1001
    }
}
