package com.petorb.bridge

import android.app.Application
import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiNetworkSpecifier
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
    private val onCameraStatus: (String) -> Unit,
    private val onBridgeStatus: (String) -> Unit,
    private val onConnected: () -> Unit,
    private val onStreamingChanged: (Boolean) -> Unit,
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
    private var streamBridge: EncodedStreamBridge? = null
    private var currentCodec = "h264"

    fun scanAndConnect() {
        scope.launch {
            runCatching {
                initializeSdk()
                onCameraStatus("扫描 GO 3S…")
                val bleDevice = scanFirstGo3s()
                onCameraStatus("蓝牙连接 ${bleDevice.name}…")
                val ble = CameraDevice.get(ConnectType.BLE)
                bleCamera = ble
                ble.connectBle(bleDevice, isBleOnly = false).getOrThrow()
                ensureAuthorization(ble)
                ensureApMode(ble)
                val wifiData = ble.system.fetchWifiData().getOrThrow()
                onCameraStatus("连接 GO 3S Wi-Fi：${wifiData.ssid}")
                val network = requestCameraWifi(wifiData.ssid, wifiData.pwd)
                check(connectivityManager.bindProcessToNetwork(network)) { "cannot bind process to GO 3S Wi-Fi" }

                val wifi = CameraDevice.get(ConnectType.WIFI)
                wifiCamera = wifi
                runCatching { ble.release() }
                bleCamera = null
                wifi.connect(network.networkHandle).getOrThrow()
                val type = wifi.system.getCameraType().getOrThrow()
                check(type == CameraType.GO_3S) { "connected camera is ${type.displayName}, expected GO 3S" }
                onCameraStatus("GO 3S 已连接")
                onConnected()
            }.onFailure(::handleConnectionFailure)
        }
    }

    fun startStreaming(streamUrl: String) {
        val device = wifiCamera
        if (device == null || !device.isConnected()) {
            onError(IllegalStateException("GO 3S 尚未连接"))
            return
        }
        if (streamListener != null) return

        scope.launch {
            runCatching {
                val encode = device.system.fetchVideoEncodeType().getOrThrow()
                currentCodec = if (encode == VideoEncode.ENCODE_H265) "h265" else "h264"
                val bridge = EncodedStreamBridge(
                    url = streamUrl,
                    onStatus = onBridgeStatus,
                    onError = onError,
                )
                streamBridge = bridge
                bridge.connect()

                val listener = object : CameraStreamListener {
                    override fun onOpening() {
                        onCameraStatus("GO 3S Preview Stream 启动中…")
                    }

                    override fun onOpened() {
                        onCameraStatus("GO 3S Preview Stream 已打开 · ${currentCodec.uppercase()}")
                        device.preview.requestStreamIframe()
                    }

                    override fun onIdle() {
                        onCameraStatus("GO 3S Preview Stream 空闲")
                    }

                    override fun onParamsChanged(paramsUpdate: PreviewStreamParamsUpdate) {
                        if (paramsUpdate.previewWidth <= 0 || paramsUpdate.previewHeight <= 0) return
                        bridge.setStreamMetadata(
                            codec = currentCodec,
                            width = paramsUpdate.previewWidth,
                            height = paramsUpdate.previewHeight,
                            fps = paramsUpdate.previewFps,
                        )
                        onCameraStatus(
                            "GO 3S 实时流 · ${paramsUpdate.previewWidth}×${paramsUpdate.previewHeight} ${paramsUpdate.previewFps} FPS · ${currentCodec.uppercase()}",
                        )
                        device.preview.requestStreamIframe()
                    }

                    override fun onStreamDataNotify(streamData: PreviewStreamFrame) {
                        if (!streamData.type.isVideo) return
                        bridge.sendEncodedVideo(streamData.data)
                    }
                }
                streamListener = listener
                device.preview.init(application)
                device.preview.registerCameraStreamListener(listener)
                device.preview.startStream()
                onStreamingChanged(true)
            }.onFailure { error ->
                stopStreamingInternal(device)
                onStreamingChanged(false)
                onError(error)
            }
        }
    }

    fun stopStreaming() {
        val device = wifiCamera ?: return
        stopStreamingInternal(device)
        onStreamingChanged(false)
        onCameraStatus("GO 3S 已连接 · 实时流已停止")
    }

    fun disconnect() {
        wifiCamera?.let(::stopStreamingInternal)
        cleanupConnection()
        onStreamingChanged(false)
        onCameraStatus("GO 3S 已断开")
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
                    onCameraStatus("请在 GO 3S 上确认连接授权…")
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

    private fun stopStreamingInternal(device: CameraDevice) {
        streamListener?.let { listener -> runCatching { device.preview.unregisterCameraStreamListener(listener) } }
        streamListener = null
        runCatching { device.preview.stopStream() }
        streamBridge?.close()
        streamBridge = null
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

    private fun handleConnectionFailure(error: Throwable) {
        onError(error)
        onCameraStatus("GO 3S 连接失败")
        cleanupConnection()
    }

    companion object {
        private const val BLE_SCAN_MS = 10_000L
        private const val AUTH_TIMEOUT_MS = 30_000L
    }
}
