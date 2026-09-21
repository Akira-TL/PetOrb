# PetOrb

PetOrb 是面向影石智能影像挑战赛的低干预宠物口腔影像采样与风险初筛系统。

当前软件主链：

```text
GO 3S → Android Camera Bridge → FastAPI → external detector → Detection Workbench
```

## Detector contract

模型队友使用 `docs/api/ai-detector-contract.md` 作为 HTTP 联调协议。

## Development

### 1. Server

```bash
cd apps/server
uv sync --dev
cp .env.example .env
uv run uvicorn petorb_server.main:app --reload --host 0.0.0.0 --port 8010
```

### 2. Web

```bash
cd apps/web
corepack pnpm install
cp .env.example .env.local
corepack pnpm dev
```

打开 `http://localhost:3000`。

依赖安装完成后，也可以从仓库根目录同时启动：

```bash
./scripts/dev.sh
```

## Validation

```bash
cd apps/server && uv run pytest
cd apps/web && corepack pnpm lint && corepack pnpm build
```

### 3. Android Camera Bridge

```bash
cd apps/android-camera-bridge
./gradlew testDebugUnitTest assembleDebug
```

Debug APK 输出到：

```text
apps/android-camera-bridge/app/build/outputs/apk/debug/app-debug.apk
```

Bridge 默认面向 Android 29+，服务端地址可在 APK 状态页中修改；比赛 FastAPI 端口固定使用 `8010`。Camera Bridge 已接入 GO 3S Preview Stream；真机参数仍需在现场完成 smoke 验证。

## Android Camera Bridge / GO 3S

比赛版 Android Bridge 使用 Insta360 Camera SDK 2.1.5，只负责：

```text
GO 3S BLE 授权
→ 相机 Wi-Fi
→ PreviewStreamFrame (H.264/H.265)
→ Android MediaCodec
→ 5 秒内约 2 FPS / 最多 10 张 JPEG
→ 本地短缓存
→ 电脑热点 FastAPI :8010
```

### Insta360 Maven 凭据

不要把比赛 SDK 仓库凭据提交到 Git。二选一：

```bash
export INSTA360_MAVEN_USERNAME='...'
export INSTA360_MAVEN_PASSWORD='...'
```

或：

```bash
cd apps/android-camera-bridge
cp insta360.properties.example insta360.properties
# 填写比赛方提供的 username / password
```

`insta360.properties` 已被 `.gitignore` 排除。

### 构建

```bash
cd apps/android-camera-bridge
./gradlew testDebugUnitTest assembleDebug
```

Debug APK：

```text
apps/android-camera-bridge/app/build/outputs/apk/debug/app-debug.apk
```

### 现场操作

1. 手机授予蓝牙和附近 Wi-Fi 权限；
2. 点击“扫描并连接 GO 3S”；
3. GO 3S 出现授权提示时，在相机端确认；
4. 点击“采样 5 秒”；
5. Bridge 获得最多 10 张 JPEG 后释放相机 Wi-Fi；
6. 确认手机回到比赛电脑热点；
7. FastAPI 地址默认使用 Windows 热点常见网关 `http://192.168.137.1:8010`，现场可直接修改；
8. 点击“上传 / 重试”。
