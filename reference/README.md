# Imported PetOrb Code Package

本目录来自 2026-09-23 收到的 `petorb.zip`，用于保留现场代码、模型权重和旧实现作为参考/兜底。

- `petorb_3070_deploy/`：YOLO11m-OBB 权重、旧 8080/8081 PC 检测服务、用户 Web、DRBNet × YOLO 实验代码和交接文档。
- `AndroidSDKDemo/`：修改过的 Insta360 Android SDK Demo，包含旧 `PcDetectBridge.kt` PixelCopy JPEG → adb reverse 方案。

当前正式主链仍以仓库根目录 `README.md` 和 `docs/architecture/realtime-pipeline.md` 为准：GO 3S 编码 PreviewStream → Android raw bridge → USB/ADB reverse → PC FFmpeg 30 FPS → local AI 10 FPS。

导入时已移除 Android Demo 中内嵌的 Insta360 Maven 凭据，改为读取环境变量 `INSTA360_MAVEN_USERNAME` / `INSTA360_MAVEN_PASSWORD`。
