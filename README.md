# PetOrb

PetOrb 是面向影石智能影像挑战赛的宠物口腔实时影像采集与 AI 风险初筛系统。

## 当前主架构

```text
GO 3S
→ Android Camera Bridge
→ USB / ADB reverse
→ FastAPI + FFmpeg
→ 30 FPS Web 实时画面
→ 每 3 帧抽 1 帧
→ 10 FPS 本机 Detector
→ OBB 实时叠框 + 风险 / 就医建议
```

详细架构：`docs/architecture/realtime-pipeline.md`。

### 为什么还需要 Android

当前 GO 3S 使用官方 Android Camera SDK 2.1.5 获取 Preview Stream。Android 只做相机连接和 H.264/H.265 原始码流转发，不再本地 MediaCodec 解码或 JPEG 批次上传。

手机 Wi-Fi 始终连接 GO 3S；手机到电脑的数据通过 USB/ADB reverse，因此两张网络不冲突。

---

## 1. 本地 Detector

比赛版默认 Detector 与 PetOrb 跑在同一台电脑：

```text
http://127.0.0.1:9000
```

真实接口：`docs/api/ai-detector-contract.md`。

当前模型输出：

```text
gingi  → 牙龈炎 / 红龈
sarro  → 牙结石
```

每个目标返回 OBB：

```text
bbox.x1,y1
bbox.x2,y2
bbox.x3,y3
bbox.x4,y4
```

Web 按 1→2→3→4 连成 polygon，不转成轴对齐矩形。

---

## 2. 比赛电脑配置

```bash
cp demo.env.example demo.env
```

默认核心配置：

```text
PETORB_DETECTOR_URL=http://127.0.0.1:9000
PETORB_API_PORT=8010
PETORB_WEB_PORT=3000
PETORB_FFMPEG_BIN=ffmpeg
PETORB_STREAM_DISPLAY_FPS=30
PETORB_STREAM_INFERENCE_FPS=10
```

电脑需要：

```text
Python + uv
Node.js + corepack/pnpm
JDK 17+
Android SDK / adb
FFmpeg
```

---

## 3. 构建

```bash
make build
```

等价于：

```bash
./scripts/build-demo.sh
```

只构建，不运行测试：

```text
uv sync
pnpm install
next build
./gradlew assembleDebug
```

Android APK：

```text
apps/android-camera-bridge/app/build/outputs/apk/debug/app-debug.apk
```

---

## 4. 启动 PetOrb PC

先启动本地 Detector，然后：

```bash
make demo
```

服务：

```text
Web      http://127.0.0.1:3000
FastAPI  http://127.0.0.1:8010
Detector http://127.0.0.1:9000
```

检查：

```bash
make status
```

停止：

```bash
make stop
```

日志：

```text
logs/demo/server.log
logs/demo/web.log
```

---

## 5. USB 码流桥

Android 端默认连接：

```text
ws://127.0.0.1:8010/ws/camera/source
```

在电脑连接手机 USB 后执行：

### Linux / WSL

```bash
./scripts/bridge-usb.sh
```

### Windows PowerShell

```powershell
.\scripts\bridge-usb.ps1
```

本质命令：

```bash
adb reverse tcp:8010 tcp:8010
```

如果你的 ADB server 不是 5037：

```bash
ADB_SERVER_PORT=5038 ./scripts/bridge-usb.sh
```

或：

```powershell
.\scripts\bridge-usb.ps1 -AdbServerPort 5038
```

---

## 6. Android Camera Bridge

Camera Bridge 当前流程：

```text
扫描 GO 3S
→ BLE 连接
→ 相机端确认授权
→ GO 3S AP / Wi-Fi
→ CameraDevice(WIFI)
→ PreviewStreamFrame
→ H.264/H.265 binary WebSocket
→ USB/ADB reverse
→ PC :8010
```

APK 页面只有：

```text
相机状态
电脑桥状态
WebSocket 地址
开始实时桥接
停止实时桥接
最近错误
```

### Insta360 Maven 凭据

```bash
cd apps/android-camera-bridge
cp insta360.properties.example insta360.properties
```

填写比赛方提供的 Maven 凭据。该文件已被 Git 忽略。

---

## 7. 电脑实时管线

Android source WebSocket：

```text
/ws/camera/source
```

浏览器 viewer WebSocket：

```text
/ws/camera/view
```

FastAPI 将 H.264/H.265 持续写入 FFmpeg，FFmpeg 输出约 30 FPS MJPEG。

```text
decoded frame 1 ─► Web
frame 2         ─► Web
frame 3         ─► Web + AI
frame 4         ─► Web
frame 5         ─► Web
frame 6         ─► Web + AI
...
```

AI 队列是有界队列，跟不上时丢旧帧，不堆积实时延迟。

---

## 8. Web

比赛正式 UI 只有一个页面。

左侧：

```text
30 FPS 实时画面
+ 最新 OBB polygon
+ label / confidence
```

右侧：

```text
最新 AI 帧
AI 实际 FPS
检测结果
风险等级
总体判断
是否建议人工检查 / 就医
```

页面固定声明：

> PetOrb 提供辅助风险观察，不构成医疗诊断。

---

## 9. 真机联调

代码完成后，GO 3S 真机验证继续记录在 GitHub Issue #15。

现场最短流程：

```text
1. clone PetOrb
2. 配 Insta360 Maven credentials
3. 安装 FFmpeg / Android SDK / adb
4. make build
5. 启动本地 Detector :9000
6. make demo
7. USB 连接 Android，执行 bridge-usb
8. 安装 Camera Bridge APK
9. Android 连接 GO 3S
10. 点击“开始实时桥接”
11. 浏览器打开 :3000
12. 调实际 FPS / 编码 / FFmpeg 参数
```

---

## 10. 已整合的 2026-09-23 代码包

Windows 微信收到的 `petorb.zip` 已整合进仓库，同时保留当前实时 30/10 FPS 主架构。

### 本地 Detector（已接入主链）

```text
apps/detector/
```

模型权重来自导入包：

```text
reference/petorb_3070_deploy/weights/best.pt
```

RTX 3070 现场机先按 CUDA 环境安装 PyTorch，再安装：

```powershell
python -m pip install -r apps\detector\requirements.txt
```

启动：

```bash
make detector
```

或 Windows：

```powershell
.\scripts\run-detector.ps1
```

然后 Detector 位于：

```text
http://127.0.0.1:9000
```

### 原代码包参考实现

完整电脑端交付包保留在：

```text
reference/petorb_3070_deploy/
```

其中包含：

- `weights/best.pt` YOLO11m-OBB 权重；
- `scripts/` 旧 JPEG / 8080 检测服务和验证脚本；
- `web/` 旧技术页和用户页；
- `drbnet_yolo_bridge/` DRBNet × YOLO 结构实验；
- 原交接文档和启动说明。

修改过的 Insta360 官方 Demo 保留在：

```text
reference/AndroidSDKDemo/
```

其中包括旧 `PcDetectBridge.kt` PixelCopy JPEG 传输方案，可作为现场 fallback/reference；它**不是**当前实时 raw H.264/H.265 主链。参考 Demo 中原先内嵌的 Maven 凭据已移除，改为从环境变量读取。
