# PetOrb 交接文档

日期：2026-09-23
本机工程：`F:\work\petorb_3070_deploy`
手机工程：`F:\work\AndroidSDKDemo`
方案：**GO 3S → 手机 Demo（Wi‑Fi 预览）→ USB/adb JPEG → 电脑 YOLO11m-OBB**

---

## 1. 系统在干什么

PetOrb 做口腔辅助风险观察（牙结石 / 口腔溃疡相关区域），**不构成医疗诊断**。

链路：

```
GO 3S  --Wi-Fi预览-->  手机 Insta360 Demo
                         | PixelCopy JPEG ~8 FPS
                         | 发到 http://127.0.0.1:8080/frame
手机 USB --adb reverse-->  电脑 8080
                         | YOLO11m-OBB (gingi / sarro)
                         +-- 技术端 http://127.0.0.1:8080
                         +-- 用户端 http://127.0.0.1:8081
```

相机和手机 **不能只连蓝牙**：BLE 没有预览，传不到电脑。

---

## 2. 两套电脑服务（不要同时开）

都占 **8080**，同时开会端口冲突。

| 用途 | 启动 | 结果 |
| --- | --- | --- |
| 旧检测框（OpenCV） | `scripts\start_pc_detect.ps1` | 弹出 `GO3S YOLO` 窗口 |
| 比赛网页（推荐演示） | `scripts\start_pc_detect_web.ps1` | 8080 技术端 + 8081 用户端 |

对应说明：

- 旧框：`如何启动电脑检测.md`
- 网页：`如何启动比赛界面.md`

旧框代码刻意没改：`scripts\pc_detect_server.py`、`start_pc_detect.ps1`、手机 Demo 采集逻辑保持可用。

---

## 3. 全流程演示（比赛网页）

1. 手机 USB 插电脑，打开 USB 调试。
2. GO 3S 用 **Wi‑Fi** 连手机。
3. 在 `F:\work\petorb_3070_deploy` 运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_pc_detect_web.ps1
```

等到：

```
adb reverse tcp:8080 tcp:8080 OK
listen 127.0.0.1:8080
listen 127.0.0.1:8081 user app
waiting for frames ...
```

4. 浏览器开两个页：
   - 技术端 http://127.0.0.1:8080
   - 用户端 http://127.0.0.1:8081
5. 手机打开已安装的 **Insta360 Demo** → 预览出画 → 点 **传到电脑检测**。
6. 停：手机点「停止传到电脑」，电脑 PowerShell `Ctrl+C`。拔过 USB 必须重新跑脚本（`adb reverse` 会丢）。

---

## 4. 两个网页分别是什么

### 技术端 `:8080`（`web\index.html`）

给评委 / 调试看。

- 左：实时原图 + 最新 OBB 多边形 + label/confidence
- 右：最新 AI 帧、AI 实际 FPS、检测列表、风险、总体判断、是否建议人工检查 / 就医
- 页脚固定：PetOrb 提供辅助风险观察，不构成医疗诊断。

手机 App 未提速，送帧大约 **8 FPS**；技术页显示实际接收和实际处理 FPS。YOLO 推理耗时依机器与首次预热而变化。没有新帧时不会重复推理旧图片。

### 用户端 `:8081`（React 构建产物 `web\user-dist`）

按 2026-09-23 参考图重做的手机宽度页面。源码位于 `web\user-app`，技术栈为 React、Vite、Tailwind CSS 4 和 MUI Icons。运行 `pnpm build` 后产物写入 `web\user-dist`，Python 服务直接提供这些文件。

- 首页以主卡片显示本次观察、设备状态和风险提示；保留宠物插画位以便后续替换图片。
- 首页实时显示 **牙龈相关区域 / 牙结石检测置信度**；尚未接收画面时显示 `--`。
- 回放：检测出结果后保存带框图，可点缩略图翻看
- 提醒 Tab：跟真实结果走
- 我的 / 预约医生 / 档案：**演示内容，没有真实功能**，页面有明确提示

用户端类别展示（仅 8081 文案，模型类名没改）：

| 模型类 | 用户端名称 |
| --- | --- |
| `gingi` | 牙龈相关区域（前端展示；API 字段仍为 `ulcer`） |
| `sarro` | 牙结石 |

---

## 5. 风险规则（写死在 `pc_detect_web_server.py`）

- 无框 → 低：未见明显异常
- 有框且最高置信 ≥ 0.40 → 中：建议人工复查；低于阈值的单框不直接判中风险
- 最高置信 ≥ 0.70 或框数 ≥ 3 → 高：建议人工检查或就医

回放不是每帧都存：有检出时大约 0.5–0.8 秒一张，内存最多约 48 张，重启服务会清空。

## 5.1 2026-09-23 网页复查与修正

- 已初始化 Git；基线提交 `3247c89`。生成图片、验证集图片和随附 adb 工具不纳入仓库，模型权重纳入仓库。
- 修正窄窗口技术页内容重叠、图片占位不消失、检测框标签难辨认，以及无新帧时重复推理导致的虚高帧数。
- 新版 React 用户页将尚未检查、检测中、画面中断明确区分，并支持回放、提醒和设备状态交互。
- 若 8080/8081 已被其他进程使用，新版服务会提示端口占用并退出。测试可传 `--port 18080 --user-port 18081`。
- `gingi` 是牙龈相关模型类别，用户页“口腔溃疡”是展示名称，页面已增加说明；仍须保留辅助观察免责声明。

---

## 6. 关键路径

| 东西 | 路径 |
| --- | --- |
| 电脑工程 | `F:\work\petorb_3070_deploy` |
| 权重 | `weights\best.pt` |
| 数据配置 | `data\data.yaml`（`gingi` / `sarro`） |
| 旧检测服务 | `scripts\pc_detect_server.py` |
| 网页检测服务 | `scripts\pc_detect_web_server.py` |
| 旧启动 | `scripts\start_pc_detect.ps1` |
| 网页启动 | `scripts\start_pc_detect_web.ps1` |
| 技术页 | `web\index.html` |
| 用户页源码 | `web\user-app` |
| 用户页构建产物 | `web\user-dist` |
| 本机 adb | `tools\platform-tools\adb.exe` |
| Python | `C:\Users\LENOVO\.conda\envs\diffir2vr\python.exe` |
| 手机工程 | `F:\work\AndroidSDKDemo` |
| 送帧代码 | `app\src\main\java\com\insta360\kmpsdk\demo\util\PcDetectBridge.kt` |
| 预览按钮 | Preview 页「传到电脑检测」 |

手机 POST：`http://127.0.0.1:8080/frame`
手机探活：`GET /health`
技术端 API：`/live.jpg` `/ai.jpg` `/api/state`
用户端 API：`/api/user` `/api/replay` `/replay/{id}.jpg`

---

## 7. 手机 App

- 工程已能编过、装到 OPPO PKJ110（`c4516c2`）。
- `compileSdk = 35`。本机曾缺 `platforms\android-35\android.jar`，已用官方包 `platform-35_r02.zip` 补进
  `C:\Users\LENOVO\AppData\Local\Android\Sdk\platforms\android-35`。
- **没有改 Insta360 SDK**（`sdk-camera` / `sdk-media`）。
- 送帧间隔约 125ms。不要为了 30 FPS 去改 Kotlin，除非明确要动现有采集。
- 用户自己用 Android Studio Run 安装；不要擅自 `adb install`，除非对方要求。

---

## 8. 本机环境注意

- conda：`diffir2vr`，torch 2.2.2+cu118，ultralytics 已装。
- Gradle 曾卡在 GitHub 下 `gradle-8.11.1-src.zip`：只影响 IDE 看源码，**不影响出 APK**。红字可忽略。
- `platforms\android-37` 是指向 `android-37.0` 的 junction，工程现用 API 35。
- 网页启动脚本必须是 **ASCII**（PowerShell 5.1 读含中文的 ps1 容易报字符串未终止）。

---

## 9. 常见故障

| 现象 | 处理 |
| --- | --- |
| `adb reverse not ready` / 手机「连不上电脑」 | USB 调试、再跑启动脚本、再点「传到电脑检测」 |
| `adb devices` 空 | 手机允许这台电脑调试 |
| 请等预览出画 | 相机必须 Wi‑Fi 或 USB，不能仅 BLE |
| 8080 被占用 | 两套服务互斥，先 `Ctrl+C` 再开另一套 |
| 用户端回放是空的 | 还没检出框，或服务刚重启 |

---

## 10. 不要随便改的

- `scripts\pc_detect_server.py` 和 `start_pc_detect.ps1`：保证旧检测框还能按 `如何启动电脑检测.md` 启动。
- `web\index.html`：比赛技术页布局。
- Insta360 SDK、连相机流程。
- 权重类名仍是 `gingi` / `sarro`；中文名只在用户端映射。

页面和对外话术必须保留：

> PetOrb 提供辅助风险观察，不构成医疗诊断。

---

## 11. 建议下一步（未做）

- 手机提到 ~30 FPS（要改 `PcDetectBridge`，会动现有 Demo）。
- 回放落到磁盘（现在只在内存）。
- 用户端「预约 / 档案」仍是演示内容；首页、回放、提醒和设备状态弹窗已接入。
- 口腔溃疡是产品文案，对应训练类是 `gingi`（牙龈相关），对外需说清楚这是辅助观察。
