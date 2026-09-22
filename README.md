# PetOrb

PetOrb 是面向影石智能影像挑战赛的低干预宠物口腔影像采样与风险初筛系统。

比赛版软件只保留一条主链：

```text
GO 3S
→ Android Camera Bridge
→ 5 秒采样 / 最多 10 张 JPEG
→ FastAPI :8010
→ 团队外部 Detector
→ 多帧聚合 / 最多 3 张证据帧
→ 单页 Detection Workbench :3000
```

Web 左侧展示图像和检测框，右侧展示结构化观察结果、风险等级和是否建议进一步人工检查/就医。PetOrb 不输出具体药物、剂量或治疗处方。

## 1. Detector 接口

模型队友统一使用：

```text
docs/api/ai-detector-contract.md
```

核心协议：

```http
POST /v1/detect
Content-Type: multipart/form-data
```

PetOrb 每次 POST 一张 JPEG，Detector 返回原图坐标系下的：

```text
label + confidence + OBB bbox (x1,y1 ... x4,y4)
```

风险判断、证据帧选择和就医建议由 PetOrb 服务端负责。

## 2. 比赛电脑配置

复制配置模板：

```bash
cp demo.env.example demo.env
```

默认配置：

```text
FastAPI:       0.0.0.0:8010
Web:           0.0.0.0:3000
Detector:      由 demo.env 的 PETORB_DETECTOR_URL 配置
Android 上传:  http://192.168.137.1:8010
```

如果 Detector 在队友电脑或其他服务地址，只改：

```bash
PETORB_DETECTOR_URL=https://<当前-detector-tunnel>
```

Android Camera Bridge 的 FastAPI 地址可直接在 APK 状态页修改，因此现场热点网关不是 `192.168.137.1` 时不需要重新编译 APK。

Detector 健康检查使用 `GET /health`；只有返回 `status: ok` 才继续传图。Detector HTTP timeout 当前按真实接口设为 60 秒。

## 3. 一键构建

```bash
./scripts/build-demo.sh
```

或：

```bash
make build
```

这个命令只做构建，不运行测试：

```text
Python dependencies → uv sync
Web dependencies    → pnpm install
Web production      → next build
Android Bridge      → assembleDebug
```

主要输出：

```text
apps/web/.next/
apps/android-camera-bridge/app/build/outputs/apk/debug/app-debug.apk
```

## 4. 一键启动比赛电脑

```bash
./scripts/run-demo.sh
```

或：

```bash
make demo
```

启动后：

```text
Web       http://127.0.0.1:3000
FastAPI   http://127.0.0.1:8010
```

运行日志：

```text
logs/demo/server.log
logs/demo/web.log
```

运行数据：

```text
.data/demo/
```

停止：

```bash
./scripts/stop-demo.sh
```

服务状态：

```bash
./scripts/status-demo.sh
```

## 5. Web 演示流程

比赛 Web 只有一个正式页面。

### 未开始

```text
READY
```

点击创建检查后，等待 Camera Bridge 上传图像。

### 接收与分析

```text
READY
→ RECEIVING
→ ANALYZING
→ COMPLETED
```

任何真实链路错误：

```text
FAILED
```

不生成 Mock 或静默假结果。

### COMPLETED 页面

左侧：

```text
证据帧
+ OBB 四点 polygon
+ label
+ confidence
```

右侧：

```text
采样质量
检测发现
总体风险
是否建议人工检查 / 就医
非诊断性护理建议
```

页面固定显示：

> PetOrb 提供辅助风险观察，不构成医疗诊断。

## 6. Android Camera Bridge

Android Bridge 不是 PetOrb 业务 App，只负责：

```text
GO 3S
→ Camera SDK 2.1.5
→ PreviewStreamFrame
→ MediaCodec
→ JPEG
→ FastAPI
```

### Insta360 Maven 凭据

不要把比赛 SDK 仓库凭据提交到 Git。

使用环境变量：

```bash
export INSTA360_MAVEN_USERNAME='...'
export INSTA360_MAVEN_PASSWORD='...'
```

或创建本机文件：

```bash
cd apps/android-camera-bridge
cp insta360.properties.example insta360.properties
```

填写比赛方提供的 Maven 用户名和密码。`insta360.properties` 已被 Git 忽略。

### Camera Bridge 已实现流程

```text
扫描 GO 3S
→ BLE 连接
→ GO 3S 授权
→ 相机 AP 模式
→ Android 加入 GO 3S Wi-Fi
→ CameraDevice(WIFI)
→ PreviewStreamFrame
→ H.264 / H.265 参数集解析
→ Android MediaCodec
→ YUV_420_888
→ JPEG
→ 5 秒内约 2 FPS，最多 10 张
→ 本地短缓存
→ 释放 GO 3S 网络
→ 手机回到电脑热点
→ multipart POST /api/ingest
```

Bridge 状态页只显示：

```text
相机状态
缓存帧数
FastAPI 地址
上传状态
最近错误
```

### APK 构建

```bash
make android
```

输出：

```text
apps/android-camera-bridge/app/build/outputs/apk/debug/app-debug.apk
```

## 7. 拿到 GO 3S 后的现场步骤

真机联调已经从软件开发主线中拆出，记录在 GitHub Issue #15。

硬件到手后执行：

1. Android 手机安装 Camera Bridge APK；
2. 打开 GO 3S；
3. Bridge 点击“扫描并连接 GO 3S”；
4. GO 3S 出现授权提示时确认；
5. 点击“采样 5 秒”；
6. 等待最多 10 张 JPEG 写入缓存；
7. 手机回到比赛电脑热点；
8. Web 创建一次 Sampling Session；
9. Bridge 确认 FastAPI 地址并点击“上传 / 重试”；
10. Web 等待 `COMPLETED`，查看 OBB 四点目标区域、风险判断和就医建议。

## 8. 开发结构

```text
apps/
├── android-camera-bridge/   GO 3S 相机适配和 JPEG 上传
├── server/                  FastAPI / SQLite / Detector adapter / 风险聚合
└── web/                     Next.js 单页 Detection Workbench

scripts/
├── build-demo.sh
├── run-demo.sh
├── status-demo.sh
└── stop-demo.sh
```

当前软件开发 Spec：GitHub Issue #9。

真机硬件验收：GitHub Issue #15。
