# PetOrb 外部口腔检测 API

版本：按 2026-09-22 团队真实 Detector 接口对齐。

## 当前服务

模型运行在另一台电脑。PetOrb 只提交 JPEG 并接收 JSON，不接收返回图片，也不从 Detector 接收诊断文字。

当前服务地址属于临时 Cloudflare tunnel，不写死在 Git；比赛电脑通过 `demo.env` 的 `PETORB_DETECTOR_URL` 配置。

无 API key。

## 健康检查

```http
GET /health
```

正常返回形状：

```json
{
  "status": "ok",
  "model": "petorb-oral-detector",
  "version": "yolo11m-obb-2026-09-18"
}
```

`status != "ok"` 时不要发检测请求。

## 检测请求

```http
POST /v1/detect
Content-Type: multipart/form-data
```

表单：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `image` | 是 | 原始 JPEG 文件，不要先改成 PNG，也不要先画框 |
| `request_id` | 否 | 任意字符串；传入时响应会原样返回 |

限制：

- 只接受 JPEG；
- 单张不超过 5 MB；
- 一次只传一张；
- PetOrb timeout 使用 60 秒。

## 成功响应

HTTP `200 OK`：

```json
{
  "request_id": "01_open_mouth",
  "image": {
    "width": 1920,
    "height": 1080
  },
  "detections": [
    {
      "label": "gingi",
      "confidence": 0.8432,
      "bbox": {
        "x1": 1402,
        "y1": 175,
        "x2": 1369,
        "y2": 0,
        "x3": 1115,
        "y3": 29,
        "x4": 1148,
        "y4": 219
      }
    }
  ],
  "model": {
    "name": "petorb-oral-detector",
    "version": "yolo11m-obb-2026-09-18"
  },
  "latency_ms": 29
}
```

## `bbox`：OBB 四角，不是轴对齐矩形

虽然字段名叫 `bbox`，其内容实际是旋转框（OBB）的四个角：

```text
(x1, y1)
(x2, y2)
(x3, y3)
(x4, y4)
```

约定：

- 坐标单位是原始 JPEG 像素；
- 原点是左上角 `(0,0)`；
- `x` 范围 `0..image.width`；
- `y` 范围 `0..image.height`；
- 四点按框的角顺序返回；
- 不保证第一个点是左上角；
- Web 必须按 `1 → 2 → 3 → 4 → 1` 连接成四边形；
- **禁止把它收成横平竖直矩形。**

PetOrb Server 保留这 8 个值，Web 再转换为 SVG polygon。

## label

真实模型当前只有两个 label：

| label | 含义 | PetOrb 展示 |
| --- | --- | --- |
| `gingi` | 牙龈炎 / 红龈 | 牙龈炎 / 红龈 |
| `sarro` | 牙结石 | 牙结石 |

PetOrb 当前产品级风险映射：

- `gingi` → `veterinary_review_recommended`
- `sarro` → `attention_recommended`

这是 PetOrb 的产品分诊逻辑，不是 Detector 返回的医疗诊断。

## confidence

范围固定 `0.0 .. 1.0`。

正确：

```json
"confidence": 0.8432
```

不使用 `84` 或 `"84%"`。

## 无检测目标

无目标仍然是成功：

```json
{
  "detections": []
}
```

PetOrb 不把空数组当接口错误。

## 错误

已知 HTTP 语义：

| HTTP | code / 含义 |
| ---: | --- |
| 400 | `INVALID_IMAGE` |
| 413 | `IMAGE_TOO_LARGE` |
| 415 | `UNSUPPORTED_MEDIA_TYPE` |
| 404 | 路径错误；检测必须 POST `/v1/detect` |
| 503 | `MODEL_NOT_READY` |

## 时延

模型本身通常是几十毫秒；Cloudflare tunnel 的网络等待可能明显更长。因此 PetOrb 将 Detector HTTP timeout 设置为 60 秒，并单独保留 Detector 返回的 `latency_ms` 作为模型推理时间参考。

## PetOrb 职责边界

Detector 负责：

```text
JPEG
→ detections[]
→ label
→ confidence
→ OBB bbox 四角
```

PetOrb 负责：

```text
Camera Bridge
→ JPEG 批次
→ 单张调用 Detector
→ 多帧聚合
→ 证据帧
→ OBB polygon 绘制
→ 风险等级
→ 是否建议人工检查 / 就医
```
