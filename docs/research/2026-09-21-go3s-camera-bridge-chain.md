# GO 3S Camera Bridge 最小调用链

## 研究问题

在比赛 SDK 2.1.5 下，如果 PetOrb Android 端只负责 **GO 3S → 图像 → PetOrb Server**，最少需要哪些 SDK API；哪些旧 PRD 功能可以彻底删除？

## 结论

Camera Bridge 不需要录像、相机媒体库、文件下载、直播 UI 或 Media SDK。最小链路是：

```text
BLE 扫描 / 连接
  ↓
读取 GO 3S Wi-Fi SSID / password
  ↓
确保相机 Wi-Fi = AP
  ↓
Android WifiNetworkSpecifier 加入相机热点
  ↓
CameraDevice(WIFI).connect(networkHandle)
  ↓
device.preview.init(context)
  ↓
registerCameraStreamListener
  ↓
startStream
  ↓
onStreamDataNotify(PreviewStreamFrame)
  ↓
只取 video frame bytes
  ↓
Android MediaCodec 解 H.264 / H.265
  ↓
抽样 1–2 FPS
  ↓
YUV/RGB → JPEG
  ↓
短暂缓存 → HTTP POST 到 PetOrb Server
```

Camera Bridge 的职责到这里结束。

## 证据

### 1. SDK 2.1.5 对 GO 3S 是显式支持

比赛包 `Android-SDK-2.1.5.zip` 对应 Maven 坐标 `com.arashivision.sdk:sdk-camera:2.1.5`。其 sources 中存在：

- `config/go3s/Go3SCameraConfig.kt`
- `support/device/Go3SSupportConfig.kt`

`Go3SSupportConfig` 明确设置 `PreviewGyroType.GO3S`，并给 GO 3S 定义预览参数。默认非 live/record 预览按相机状态选择 640×480 / 640×360 等 30 FPS 流；因此桥接层没有必要为了取图主动进入录像或直播业务。

来源：比赛飞书附件 `Android-SDK-2.1.5.zip`：<https://arashivision.feishu.cn/wiki/YfiOwnwLeivnB3k2vJycWwyLnxc>。

### 2. 连接只需要 BLE 引导一次，再切 Wi-Fi

比赛 Demo `ConnectionViewModel.kt` 的已验证流程：

1. `CameraDevice.get(ConnectType.BLE)`；
2. BLE connect；
3. `ensureApMode()` 确保相机 `WiFiData.Mode.AP`；
4. `bleCamera.system.getWifiData()` 读取相机 SSID/password；
5. Android `WifiNetworkSpecifier` 加入相机热点；
6. `CameraWifiProcessNetworkBinder.bindProcessToNetwork()`；
7. 释放 BLE；
8. `CameraDevice.get(ConnectType.WIFI)`；
9. `wifiCameraDevice.connect(network.networkHandle)`。

官方 V2 文档给出的 BLE → Wi-Fi bootstrap 流程完全一致。

来源：<https://insta360develop.github.io/Insta360-Developer_Docs/en/x/android/camera-integration/>。

### 3. 预览流可以直接取得原始编码字节

Camera SDK 2.1.5 的 `CameraPreview` 接口：

- `init(context)`
- `registerCameraStreamListener(listener)`
- `startStream()`
- `requestStreamIframe()`
- `stopStream()`

`CameraStreamListener.onStreamDataNotify(streamData)` 返回 `PreviewStreamFrame`；其中：

```text
data: ByteArray
timestamp: Long
type: PreviewStreamType
```

`PreviewStreamType` 能区分 `VIDEO / VIDEO_L / VIDEO_R / AUDIO / GYRO`，并提供 `isVideo`。

比赛 Demo 的 `LiveStreamFragment.kt` 也直接在 `onStreamDataNotify` 中统计 `streamData.data.size`，说明该回调就是上层拿原始预览码流的稳定入口。

来源：SDK 2.1.5 sources：

- `api/CameraPreview.kt`
- `api/preview/CameraStreamListener.kt`
- `api/preview/PreviewStreamFrame.kt`
- Demo `ui/livestream/LiveStreamFragment.kt`

官方接口参考：<https://insta360develop.github.io/Insta360-Developer_Docs/en/x/android/camera-api/>。

### 4. `PreviewStreamFrame.data` 不是 JPEG，而是 H.264/H.265 视频码流

SDK source 明确存在：

- `VideoEncode.ENCODE_H264`
- `VideoEncode.ENCODE_H265`
- `CameraSystem.getVideoEncodeType()` / `fetchVideoEncodeType()`
- `PreviewCodecDetector` 对 H.264 SPS/PPS/IDR 与 H.265 VPS/SPS/PPS 做 NAL 检测
- `CameraPreview.startStream()` 会自动同步当前视频编码配置

`PreviewStreamFrame` 源码注释还明确说明：Demo 中该数据在送入 **MediaCodec** 解码前，会把 timestamp 转为微秒。

因此 PetOrb 不能把 `streamData.data` 直接当图片 POST。Bridge 需要一个很薄的 Android 视频解码层：

```text
H.264 / H.265 access units
       ↓
MediaCodec
       ↓
YUV / RGB frame
       ↓
JPEG
```

### 5. 不需要依赖 Media SDK

比赛文档明确说明 GO 系列使用 **Camera SDK**；Media SDK 是 X 系列全景素材处理能力。PetOrb 不做全景拼接，也不需要播放器 UI，因此桥接层直接使用 Camera SDK 原始预览流 + Android 系统 `MediaCodec` 即可。

这也避免把大量与 PetOrb 无关的播放器、拼接、导出能力带入 APK。

## MVP 实现边界

### 保留

- SDK 初始化；
- BLE 扫描/连接；
- 自动切 GO 3S Wi-Fi；
- Wi-Fi CameraDevice；
- CameraStreamListener；
- H.264/H.265 解码；
- 1–2 FPS 抽样；
- JPEG 压缩；
- 本地短缓存；
- HTTP POST；
- 断开、重连和最小状态提示。

### 删除

- 拍照/录像控制；
- Gallery；
- 相机文件枚举；
- 视频下载；
- RTMP live；
- 相机设置页；
- Media SDK；
- 播放器；
- Rescue Mode 业务 UI；
- AI 推理。

## 推荐的 Bridge 内部接口

```kotlin
interface CameraBridge {
    suspend fun connect(): Result<Unit>
    fun startSampling(onJpeg: (JpegFrame) -> Unit)
    fun stopSampling()
    suspend fun disconnect()
}

data class JpegFrame(
    val bytes: ByteArray,
    val capturedAtMs: Long,
    val width: Int,
    val height: Int,
)
```

HTTP 上传协议由后续“PetOrb 服务端与外部 AI 分析服务接口契约”票决定，Camera Bridge 不自行定义业务 JSON。

## 首个真机验收点

没有 GO 3S 真机时可以完成连接状态机、decoder、JPEG 编码器和 HTTP uploader 的绝大部分代码；真机到手后只需要验证：

1. SDK 是否正确识别 GO 3S；
2. `onParamsChanged` 实际返回的宽高/FPS；
3. `onStreamDataNotify` 的实际编码（H.264/H.265）与数据分包形态；
4. MediaCodec 首帧是否需要额外 CSD/NAL 聚合；
5. 1–2 FPS JPEG 抽样时的端到端延迟与清晰度。

这些是真机验证，不再是架构决策。
