# PetOrb 实时 30/10 FPS 架构

当前比赛主链：

```text
GO 3S
  │ Wi-Fi / Insta360 Camera SDK 2.1.5
  │ H.264 / H.265 PreviewStreamFrame
  ▼
Android Camera Bridge
  │ 不解码、不转 JPEG
  │ WebSocket binary
  │ USB + adb reverse tcp:8010 tcp:8010
  ▼
PetOrb FastAPI :8010
  │ encoded stream → FFmpeg
  ▼
FFmpeg
  │ MJPEG ~30 FPS
  ├──────────────► /ws/camera/view ─► Web Canvas 30 FPS
  │
  └─ 每 3 帧抽 1 帧 ─► bounded AI queue ─► local Detector ~10 FPS
                                              │
                                              ▼
                                      gingi / sarro + OBB
                                              │
                                              ▼
                                      Web 实时 OBB + 风险建议
```

## Android 的职责

- BLE 扫描、连接和 GO 3S 授权；
- 切到 GO 3S AP / Wi-Fi CameraDevice；
- `CameraPreview.startStream()`；
- 把 `PreviewStreamFrame.data` 原样经 WebSocket 发到电脑；
- 不使用 MediaCodec，不做 JPEG，不跑 AI，不保存批次。

默认 source URL：

```text
ws://127.0.0.1:8010/ws/camera/source
```

这个 `127.0.0.1` 是 Android 设备自身，通过：

```bash
adb reverse tcp:8010 tcp:8010
```

转发到电脑的 FastAPI 8010。因此手机 Wi-Fi 可以始终绑定 GO 3S。

## PC 的职责

FastAPI 接收编码流后启动 FFmpeg：

```text
H.264/H.265 stdin
→ decode
→ fps=30
→ MJPEG image2pipe
```

每个 JPEG 分配 `frame_id`：

- 全部帧发给 Web；
- 默认每 3 帧取 1 帧进入 Detector；
- AI 队列最大 2，满时丢最旧帧，不允许实时检测越来越滞后。

## Web 的职责

WebSocket `/ws/camera/view` 同时承载：

- binary：`4-byte big-endian frame_id + JPEG`；
- text JSON：stream status / inference / error。

Canvas 负责：

```text
JPEG 画面
+ 最新 OBB polygon
+ label / confidence
```

右栏显示最新 AI 帧的风险等级、总体判断与是否建议进一步检查/就医。

## Detector

Detector 默认本机部署：

```text
http://127.0.0.1:9000
```

真实协议见 `docs/api/ai-detector-contract.md`。
