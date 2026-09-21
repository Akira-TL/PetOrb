package com.petorb.bridge

import android.app.Activity
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
    private lateinit var serverUrlInput: EditText
    private lateinit var sourceStatus: TextView
    private lateinit var frameCount: TextView
    private lateinit var uploadStatus: TextView
    private lateinit var lastError: TextView
    private lateinit var uploadButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        batchStore = BatchStore(cacheDir.resolve("petorb-batch"))
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
            text = "工程状态页 · #12 使用模拟 JPEG，#13 替换为 GO 3S Preview Stream"
            textSize = 14f
            setPadding(0, dp(6), 0, dp(24))
        })

        sourceStatus = statusText("相机连接：模拟源（GO 3S 待 #13 接入）")
        frameCount = statusText("缓存帧：0 / 10")
        uploadStatus = statusText("上传：未开始")
        lastError = statusText("最近错误：无")
        listOf(sourceStatus, frameCount, uploadStatus, lastError).forEach(container::addView)

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

        val generateButton = Button(this).apply {
            text = "生成 10 张模拟采样"
            setOnClickListener { generateSampleBatch() }
        }
        container.addView(generateButton)

        uploadButton = Button(this).apply {
            text = "上传 / 重试"
            setOnClickListener { uploadCurrentBatch() }
        }
        container.addView(uploadButton)

        container.addView(TextView(this).apply {
            text = "说明：上传前请在 PetOrb Web 创建活动 Sampling Session。成功后本地批次会清空；失败时保留 JPEG，可直接重试。"
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

    private fun generateSampleBatch() {
        runCatching {
            assets.open("sample.jpg").use { input ->
                batchStore.replaceWithSamples(input.readBytes(), BatchStore.MAX_BATCH_SIZE)
            }
        }.onSuccess {
            uploadStatus.text = "上传：待发送"
            lastError.text = "最近错误：无"
            refreshFrameCount()
        }.onFailure { error ->
            lastError.text = "最近错误：${error.message}"
        }
    }

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
        frameCount.text = "缓存帧：${batchStore.listFrames().size} / ${BatchStore.MAX_BATCH_SIZE}"
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    companion object {
        private const val PREFS = "petorb-bridge"
        private const val KEY_SERVER_URL = "server-url"
        private const val DEFAULT_SERVER_URL = "http://192.168.137.1:8010"
    }
}
