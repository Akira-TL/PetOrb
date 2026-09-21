package com.petorb.bridge

import android.app.Application
import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiNetworkSpecifier
import android.os.SystemClock
import com.arashivision.inskmp.insble.data.BleDeviceCore
import com.arashivision.sdk.camera.InstaCameraSDK
import com.arashivision.sdk.camera.api.CameraDevice
import com.arashivision.sdk.camera.api.param.listener.AuthorizationListener
import com.arashivision.sdk.camera.api.preview.CameraStreamListener
import com.arashivision.sdk.camera.api.preview.PreviewStreamFrame
import com.arashivision.sdk.camera.api.preview.PreviewStreamParamsUpdate
import com.arashivision.sdk.camera.core.callback.BleScanCallback
import com.arashivision.sdk.camera.core.model.CameraType
import com.arashivision.sdk.camera.core.model.ConnectType
import com.arashivision.sdk.camera.core.model.authorization.AuthorizationOperationType
import com.arashivision.sdk.camera.core.model.authorization.AuthorizationResult
import com.arashivision.sdk.camera.core.model.authorization.AuthorizationStatus
import com.arashivision.sdk.camera.core.model.option.VideoEncode
import com.arashivision.sdk.camera.core.model.option.WiFiData
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeout
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class Go3sCameraController(
    context: Context,
    private val batchStore: BatchStore,
    private val onStatus: (String) -> Unit,
    private val onConnected: () -> Unit,
    private val onFrameCount: (Int) -> Unit,
    private val onSamplingComplete: (Int) -> Unit,
    private val onError: (Throwable) -> Unit,
) {
    private val application = context.applicationContext as Application
    private val connectivityManager = application.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var initialized = false
    private var bleCamera: CameraDevice? = null
    private var wifiCamera: CameraDevice? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var streamListener: CameraStreamListener? = null
    private var decoder: PreviewJpegDecoder? = null
    private var samplingJob: Job? = null

    fun scanAndConnect() {
        scope.launch {
            runCatching {
                initializeSdk()
                onStatus("扫描 GO 3S…")
                val bleDevice = scanFirstGo3s()
                onStatus("蓝牙连接 ${bleDevice.name}…")
                val ble = CameraDevice.get(ConnectType.BLE)
                bleCamera = ble
                ble.connectBle(bleDevice, isBleOnly = false).getOrThrow()
                ensureAuthorization(ble)
                ensureApMode(ble)
                val wifiData = ble.system.fetchWifiData().getOrThrow()
                onStatus("连接 GO 3S Wi‑Fi：${wifiData.ssid}")
                val network = requestCameraWifi(wifiData.ssid, wifiData.pwd)
                check(connectivityManager.bindProcessToNetwork(network)) { "cannot bind process to GO 3S Wi-Fi" }

                val wifi = CameraDevice.get(ConnectType.WIFI)
                wifiCamera = wifi
                runCatching { ble.release() }
                bleCamera = null
                wifi.connect(network.networkHandle).getOrThrow()
                val type = wifi.system.getCameraType().getOrThrow()
                check(type == CameraType.GO_3S) { "connected camera is ${type.displayName}, expected GO 3S" }
                onStatus("GO 3S 已连接 · 可开始 5 秒采样")
                onConnected()
            }.onFailure { error ->
                onError(error)
                onStatus("GO 3S 连接失败")
                cleanupConnection()
            }
        }
    }

    fun startFiveSecondSampling() {
        val device = wifiCamera
        if (device == null || !device.isConnected()) {
            onError(IllegalStateException("GO 3S 尚未连接"))
            return
        }
        if (samplingJob?.isActive == true) return

        batchStore.clear()
        onFrameCount(0)
        samplingJob = scope.launch {
            runCatching {
                val encode = device.system.fetchVideoEncodeType().getOrThrow()
                val codec = if (encode == VideoEncode.ENCODE_H265) VideoCodec.H265 else VideoCodec.H264
                val gate = SamplingGate(SystemClock.elapsedRealtime())
                var decoderInstance: PreviewJpegDecoder? = null
                val listener = object : CameraStreamListener {
                    override fun onOpening() {
                        onStatus("GO 3S 预览流启动中…")
                    }

                    override fun onOpened() {
                        onStatus("GO 3S 采样中 · ${if (codec == VideoCodec.H265) "H.265" else "H.264"}")
                        device.preview.requestStreamIframe()
                    }

                    override fun onIdle() = Unit

                    override fun onParamsChanged(paramsUpdate: PreviewStreamParamsUpdate) {
                        if (paramsUpdate.previewWidth <= 0 || paramsUpdate.previewHeight <= 0 || decoderInstance != null) return
                        decoderInstance = PreviewJpegDecoder(
                            videoCodec = codec,
                            width = paramsUpdate.previewWidth,
                            height = paramsUpdate.previewHeight,
                            batchStore = batchStore,
                            samplingGate = gate,
                            onFrameSaved = onFrameCount,
                            onError = onError,
                        )
                        decoder = decoderInstance
                        onStatus(
                            "GO 3S 采样中 · ${paramsUpdate.previewWidth}×${paramsUpdate.previewHeight} ${paramsUpdate.previewFps}fps",
                        )
                    }

                    override fun onStreamDataNotify(streamData: PreviewStreamFrame) {
                        if (!streamData.type.isVideo) return
                        decoderInstance?.offer(streamData.data, streamData.timestamp)
                    }
                }
                streamListener = listener
                device.preview.init(application)
                device.preview.registerCameraStreamListener(listener)
                device.preview.startStream()
                delay(SAMPLING_WINDOW_MS)
                finishSampling(device)
            }.onFailure { error ->
                onError(error)
                stopPreviewOnly(device)
                cleanupConnection()
            }
        }
    }

    fun disconnect() {
        samplingJob?.cancel()
        samplingJob = null
        wifiCamera?.let(::stopPreviewOnly)
        cleanupConnection()
        onStatus("GO 3S 已断开")
    }

    fun release() {
        disconnect()
        scope.cancel()
    }

    private fun initializeSdk() {
        if (initialized) return
        InstaCameraSDK.init(application) {
            cacheDir = application.cacheDir.absolutePath
        }
        initialized = true
    }

    private suspend fun scanFirstGo3s(): BleDeviceCore = suspendCancellableCoroutine { continuation ->
        val camera = CameraDevice.get(ConnectType.BLE)
        bleCamera = camera
        camera.scan(
            BLE_SCAN_MS,
            object : BleScanCallback {
                override fun onStarted() = Unit

                override fun onScanning(bleDevice: BleDeviceCore) {
                    if (!continuation.isActive) return
                    if (CameraType.getForSimpleName(bleDevice.name) == CameraType.GO_3S) {
                        camera.stopScan()
                        continuation.resume(bleDevice)
                    }
                }

                override fun onFinished(bleDeviceList: List<BleDeviceCore>) {
                    if (!continuation.isActive) return
                    val go3s = bleDeviceList.firstOrNull {
                        CameraType.getForSimpleName(it.name) == CameraType.GO_3S
                    }
                    if (go3s != null) continuation.resume(go3s)
                    else continuation.resumeWithException(IllegalStateException("未扫描到 GO 3S"))
                }

                override fun onError(throwable: Throwable) {
                    if (continuation.isActive) continuation.resumeWithException(throwable)
                }
            },
        )
        continuation.invokeOnCancellation { runCatching { camera.stopScan() } }
    }

    private suspend fun ensureAuthorization(device: CameraDevice) {
        val authorization = CompletableDeferred<Unit>()
        val listener = object : AuthorizationListener {
            override fun onAuthorizationResult(
                operationType: AuthorizationOperationType,
                result: AuthorizationResult,
            ) {
                when (result) {
                    AuthorizationResult.SUCCESS -> authorization.complete(Unit)
                    AuthorizationResult.REJECT -> authorization.completeExceptionally(IllegalStateException("GO 3S 授权被拒绝"))
                    AuthorizationResult.TIMEOUT -> authorization.completeExceptionally(IllegalStateException("GO 3S 授权超时"))
                    AuthorizationResult.SYSTEM_BUSY -> authorization.completeExceptionally(IllegalStateException("GO 3S 正忙，无法授权"))
                }
            }
        }
        device.registerAuthorizationListener(listener)
        try {
            when (device.checkAuthorization().getOrThrow()) {
                AuthorizationStatus.AUTHORIZED -> return
                AuthorizationStatus.UNAUTHORIZED -> {
                    onStatus("请在 GO 3S 上确认连接授权…")
                    withTimeout(AUTH_TIMEOUT_MS) { authorization.await() }
                }
                AuthorizationStatus.SYSTEM_BUSY -> error("GO 3S 正忙，无法检查授权")
            }
        } finally {
            device.unregisterAuthorizationListener(listener)
        }
    }

    private suspend fun ensureApMode(device: CameraDevice) {
        val current = device.system.fetchWifiData().getOrThrow()
        if (current.mode == WiFiData.Mode.AP) return
        device.system.setWifiMode(WiFiData.Mode.AP, "").getOrThrow()
        repeat(10) {
            delay(500)
            if (device.system.fetchWifiData().getOrThrow().mode == WiFiData.Mode.AP) return
        }
        error("GO 3S 切换 AP 模式超时")
    }

    private suspend fun requestCameraWifi(ssid: String, password: String): Network =
        suspendCancellableCoroutine { continuation ->
            val specifier = WifiNetworkSpecifier.Builder()
                .setSsid(ssid)
                .setWpa2Passphrase(password)
                .build()
            val request = NetworkRequest.Builder()
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                .setNetworkSpecifier(specifier)
                .build()
            val callback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    if (continuation.isActive) continuation.resume(network)
                }

                override fun onUnavailable() {
                    if (continuation.isActive) {
                        continuation.resumeWithException(IllegalStateException("无法加入 GO 3S Wi-Fi"))
                    }
                }
            }
            networkCallback = callback
            connectivityManager.requestNetwork(request, callback)
            continuation.invokeOnCancellation {
                if (networkCallback === callback) unregisterNetworkCallback()
            }
        }

    private suspend fun finishSampling(device: CameraDevice) {
        stopPreviewOnly(device)
        val count = batchStore.listFrames().size
        runCatching { device.disconnect().getOrThrow() }
        runCatching { device.release() }
        wifiCamera = null
        connectivityManager.bindProcessToNetwork(null)
        unregisterNetworkCallback()
        if (count == 0) {
            onError(IllegalStateException("5 秒采样未获得可解码 JPEG，请检查预览码流/MediaCodec"))
        }
        onSamplingComplete(count)
        onStatus("采样完成 · $count 张 JPEG · 请连接电脑热点后上传")
    }

    private fun stopPreviewOnly(device: CameraDevice) {
        streamListener?.let { listener -> runCatching { device.preview.unregisterCameraStreamListener(listener) } }
        streamListener = null
        runCatching { device.preview.stopStream() }
        decoder?.release()
        decoder = null
    }

    private fun cleanupConnection() {
        val wifi = wifiCamera
        wifiCamera = null
        runCatching { wifi?.release() }
        val ble = bleCamera
        bleCamera = null
        runCatching { ble?.release() }
        connectivityManager.bindProcessToNetwork(null)
        unregisterNetworkCallback()
    }

    private fun unregisterNetworkCallback() {
        val callback = networkCallback ?: return
        networkCallback = null
        runCatching { connectivityManager.unregisterNetworkCallback(callback) }
    }

    companion object {
        private const val BLE_SCAN_MS = 10_000L
        private const val AUTH_TIMEOUT_MS = 30_000L
        private const val SAMPLING_WINDOW_MS = 5_000L
    }
}
