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
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var batchStore: BatchStore
    private lateinit var cameraController: Go3sCameraController
    private lateinit var serverUrlInput: EditText
    private lateinit var sourceStatus: TextView
    private lateinit var frameCount: TextView
    private lateinit var uploadStatus: TextView
    private lateinit var lastError: TextView
    private lateinit var connectButton: Button
    private lateinit var sampleButton: Button
    private lateinit var uploadButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        batchStore = BatchStore(cacheDir.resolve("petorb-batch"))
        cameraController = Go3sCameraController(
            context = this,
            batchStore = batchStore,
            onStatus = { message -> runOnUiThread { sourceStatus.text = "相机：$message" } },
            onConnected = {
                runOnUiThread {
                    connectButton.isEnabled = false
                    sampleButton.isEnabled = true
                    lastError.text = "最近错误：无"
                }
            },
            onFrameCount = { count ->
                runOnUiThread { frameCount.text = "缓存帧：$count / ${BatchStore.MAX_BATCH_SIZE}" }
            },
            onSamplingComplete = { count ->
                runOnUiThread {
                    frameCount.text = "缓存帧：$count / ${BatchStore.MAX_BATCH_SIZE}"
                    sampleButton.isEnabled = false
                    connectButton.isEnabled = true
                    uploadButton.isEnabled = count > 0
                    uploadStatus.text = if (count > 0) "上传：待连接电脑热点后发送" else "上传：无有效 JPEG"
                }
            },
            onError = { error ->
                runOnUiThread {
                    lastError.text = "最近错误：${error.message ?: error.javaClass.simpleName}"
                    connectButton.isEnabled = true
                    sampleButton.isEnabled = false
                }
            },
        )
        setContentView(buildUi())
        refreshFrameCount()
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
            text = "GO 3S → Preview Stream → JPEG → FastAPI"
            textSize = 14f
            setPadding(0, dp(6), 0, dp(24))
        })

        sourceStatus = statusText("相机：未连接")
        frameCount = statusText("缓存帧：0 / 10")
        uploadStatus = statusText("上传：未开始")
        lastError = statusText("最近错误：无")
        listOf(sourceStatus, frameCount, uploadStatus, lastError).forEach(container::addView)

        connectButton = Button(this).apply {
            text = "扫描并连接 GO 3S"
            setOnClickListener { requestCameraPermissionsAndConnect() }
        }
        container.addView(connectButton)

        sampleButton = Button(this).apply {
            text = "采样 5 秒"
            isEnabled = false
            setOnClickListener {
                isEnabled = false
                uploadButton.isEnabled = false
                uploadStatus.text = "上传：等待采样完成"
                lastError.text = "最近错误：无"
                cameraController.startFiveSecondSampling()
            }
        }
        container.addView(sampleButton)

        container.addView(TextView(this).apply {
            text = "FastAPI 地址"
            setPadding(0, dp(20), 0, dp(6))
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        })
        serverUrlInput = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setSingleLine(true)
            setText(
                getSharedPreferences(PREFS, MODE_PRIVATE)
                    .getString(KEY_SERVER_URL, DEFAULT_SERVER_URL)
            )
        }
        container.addView(serverUrlInput, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

        uploadButton = Button(this).apply {
            text = "上传 / 重试"
            isEnabled = batchStore.listFrames().isNotEmpty()
            setOnClickListener { uploadCurrentBatch() }
        }
        container.addView(uploadButton)

        container.addView(TextView(this).apply {
            text = "流程：连接 GO 3S → 在相机上确认授权 → 采样 5 秒 → 相机网络释放 → 确认手机已回到电脑热点 → 上传。上传成功后缓存自动清空；失败会保留 JPEG，可直接重试。"
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
        if (missing.isEmpty()) {
            startCameraConnection()
        } else {
            requestPermissions(missing.toTypedArray(), CAMERA_PERMISSION_REQUEST)
        }
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
            lastError.text = "最近错误：需要蓝牙/Wi‑Fi 权限才能连接 GO 3S"
        }
    }

    private fun startCameraConnection() {
        connectButton.isEnabled = false
        sampleButton.isEnabled = false
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

    private fun uploadCurrentBatch() {
        val files = batchStore.listFrames()
        if (files.isEmpty()) {
            lastError.text = "最近错误：没有可上传的缓存 JPEG"
            return
        }
        val serverUrl = serverUrlInput.text.toString().trim().ifBlank { DEFAULT_SERVER_URL }
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_SERVER_URL, serverUrl).apply()
        uploadButton.isEnabled = false
        uploadStatus.text = "上传：发送中（${files.size} 张）"
        lastError.text = "最近错误：无"

        executor.submit {
            runCatching { MultipartBatchUploader(serverUrl).upload(files) }
                .onSuccess { result ->
                    runOnUiThread {
                        uploadButton.isEnabled = true
                        if (result.isSuccessful) {
                            batchStore.clear()
                            uploadStatus.text = "上传：成功 (${result.statusCode})"
                            lastError.text = "最近错误：无"
                            refreshFrameCount()
                        } else {
                            uploadStatus.text = "上传：失败 (${result.statusCode})，缓存已保留"
                            lastError.text = "最近错误：${result.body.take(300)}"
                            refreshFrameCount()
                        }
                    }
                }
                .onFailure { error ->
                    runOnUiThread {
                        uploadButton.isEnabled = true
                        uploadStatus.text = "上传：失败，缓存已保留"
                        lastError.text = "最近错误：${error.message}"
                        refreshFrameCount()
                    }
                }
        }
    }

    private fun refreshFrameCount() {
        val count = batchStore.listFrames().size
        frameCount.text = "缓存帧：$count / ${BatchStore.MAX_BATCH_SIZE}"
        uploadButton.isEnabled = count > 0
    }

    override fun onDestroy() {
        cameraController.release()
        executor.shutdownNow()
        super.onDestroy()
    }

    companion object {
        private const val PREFS = "petorb-bridge"
        private const val KEY_SERVER_URL = "server-url"
        private const val DEFAULT_SERVER_URL = "http://192.168.137.1:8010"
        private const val CAMERA_PERMISSION_REQUEST = 1001
    }
}
