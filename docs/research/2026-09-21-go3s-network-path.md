# GO 3S 到 PetOrb 服务端的最小网络路径

## 研究问题

比赛现场是否可以让 GO 3S 直接加入电脑热点，并由相机直接把图像发送给电脑上的 PetOrb 服务端；如果比赛 SDK 不支持这一条，应采用什么最小路径，才能只完成“取图 → 发给服务端”而不增加 Android 业务功能？

## 结论

当前比赛 SDK 2.1.5 **明确支持 GO 3S**，但现有比赛 Demo 与官方 V2 Android 集成文档验证过的普通 Wi-Fi 路径是：**GO 3S 作为 Wi-Fi AP，Android 读取相机 SSID/密码并加入相机热点**。没有找到比赛 Demo 或公开 V2 文档中“为 GO 3S 写入外部热点 SSID/密码，让 GO 3S 作为 STA 自动加入电脑热点”的已验证流程。因此，比赛主链路不把“GO 3S 直接 POST 到电脑”作为可依赖能力。

PetOrb 采用最小 **Camera Bridge**：Android 只负责从 GO 3S 取到图像并转发给电脑服务端，不承载 Rescue Mode、结果展示或 AI 逻辑。当前 MVP 只要求传图，不要求持续实时视频，所以优先采用**顺序式 store-and-forward**：Android 在相机热点上取图并本地缓存，随后自动切到电脑热点，把 JPEG/图像包 POST 到 FastAPI。这样不需要同时维持相机 Wi-Fi 与电脑热点。

如果后续必须做到连续实时转发，再单独评估第二网络通道（USB/蜂窝/特定机型 Wi-Fi sharing）；它不属于当前 MVP 的前置条件。

## 证据

### 1. 比赛包确实包含 GO 3S 专用配置

比赛附件 `Android-SDK-2.1.5.zip` 中 Demo 使用 Maven 坐标 `com.arashivision.sdk:sdk-camera:2.1.5`。对应 2.1.5 sources 中直接存在：

- `com/arashivision/sdk/camera/config/go3s/Go3SCameraConfig.kt`
- `com/arashivision/sdk/camera/support/device/Go3SSupportConfig.kt`

`Go3SSupportConfig` 还定义了 GO 3S 的预览分辨率与预览参数。因此 GO 3S 不是“推测支持”，而是 SDK 2.1.5 的显式设备配置。

来源：比赛飞书《影石赛事SDK & 开源算法开发调用指南》附件 `Android-SDK-2.1.5.zip`；比赛文档：<https://arashivision.feishu.cn/wiki/YfiOwnwLeivnB3k2vJycWwyLnxc>。

### 2. 当前官方 V2 SDK 统一覆盖 X / ACE / GO

影石当前 V2 Android SDK 文档明确说明 X、ACE、GO 共用 V2.x API，Camera SDK 提供连接、拍摄、实时预览与文件管理。

来源：Insta360 Developer Docs — Android SDK Overview：<https://github.com/Insta360Develop/Insta360-Developer_Docs/blob/main/docs/en/sdk/x-ace-go/android/guide.md>。

### 3. 比赛 Demo 的 Wi-Fi 连接是“相机 AP → Android 加入”

比赛 Demo：

`AndroidSDKDemo/app/src/main/java/com/insta360/kmpsdk/demo/ui/connection/ConnectionViewModel.kt`

关键逻辑：

- 593–604：连接普通 Wi-Fi 前显式确保相机进入 `WiFiData.Mode.AP`；
- 657–663：通过 BLE 从相机读取 Wi-Fi SSID / password；
- 663–680：Android 用系统 Wi-Fi API 连接该 SSID；
- 681–694：Android 把 SDK 连接绑定到取得的相机 Wi-Fi `Network`，再以 `ConnectType.WIFI` 建立相机连接；
- 731–779：实际使用 `WifiNetworkSpecifier` 让 Android 加入相机 SSID。

同一 Demo 的 `CameraWifiProcessNetworkBinder.kt` 也明确写着“蓝牙引导 `requestNetwork` 连上**相机热点**后绑定进程网络”。

官方 V2 文档给出的 BLE bootstrap 流程与 Demo 一致：读取相机 SSID/password → Android 加入相机 hotspot → 使用 networkHandle 建立 SDK Wi-Fi 连接。

来源：<https://insta360develop.github.io/Insta360-Developer_Docs/en/x/android/camera-integration/>。

### 4. SDK 类型中存在 STA，但没有找到 GO 3S 外部热点配置流程

2.1.5 source 中 `WiFiData.Mode` 包含：

- `AP`
- `STA`
- `P2P`
- `Android_Aware`
- `IOS_Aware`

同时 `CameraSystem.setWifiMode(mode, countryCode)` 对外暴露切换模式接口。但是在比赛 Demo 和 2.1.5 公共 source 中，没有找到 `Mode.STA` 的实际调用，也没有找到通过该 API 为相机设置目标热点 SSID/password 的配套流程。比赛 Demo 对 GO/X/ACE 的普通 Wi-Fi 路径反而主动切回 AP。

因此，`STA` 枚举的存在只能说明底层协议具有该状态，**不能作为 GO 3S 可稳定加入电脑热点的比赛级证据**。

## MVP 决策

```text
GO 3S
  │ 相机 Wi-Fi / Camera SDK
  ▼
Android Camera Bridge
  │
  ├─ 取得 JPEG / 关键图像
  ├─ 本地短暂缓存
  └─ 自动切到电脑热点
          │ HTTP POST
          ▼
      FastAPI 服务端
```

Camera Bridge 不做：

- Rescue Mode 业务界面；
- AI 推理；
- 结果解释；
- 历史记录；
- 用户管理；
- 长期媒体保存。

它只负责 **GO 3S → 图像 → PetOrb Server**。

## 尚未验证但不阻塞当前路线

- GO 3S 真机调用 `setWifiMode(STA)` 后的具体固件行为；
- 是否存在未公开/未在 Demo 中展示的 STA 凭据配置接口；
- 特定 Android 手机能否同时维持 Wi-Fi client + hotspot/Wi-Fi sharing。

这些能力如果现场验证成功可以优化链路，但不应成为 MVP 成功的必要条件。
