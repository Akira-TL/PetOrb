# PetOrb 外部检测模型 HTTP 接口协议

版本：v1

## 1. 目的

PetOrb 通过 HTTP 向团队的外部图像检测服务提交**单张 JPEG**。检测服务只负责返回该图像中的检测框、类别与置信度；风险聚合、就医建议、Web 展示与数据持久化全部由 PetOrb 服务端负责。

## 2. Endpoint

```http
POST /v1/detect
Content-Type: multipart/form-data
```

### Form 字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `image` | file | 是 | 单张 JPEG，`image/jpeg` |
| `request_id` | string | 否 | PetOrb 生成的请求 ID；若提供，响应原样返回 |

建议限制：

- 单文件不超过 5 MB；
- 只接受 JPEG；
- 一次请求只处理一张图；
- 不接受视频或 ZIP。

## 3. 成功响应

HTTP `200 OK`

```json
{
  "request_id": "9e25b6d3-8ce9-43d3-b8bf-0ea845d93f7b",
  "image": {
    "width": 1280,
    "height": 720
  },
  "detections": [
    {
      "label": "tartar_suspected",
      "confidence": 0.87,
      "bbox": {
        "x1": 412,
        "y1": 203,
        "x2": 690,
        "y2": 461
      }
    },
    {
      "label": "gingiva_redness",
      "confidence": 0.78,
      "bbox": {
        "x1": 705,
        "y1": 250,
        "x2": 1012,
        "y2": 486
      }
    }
  ],
  "model": {
    "name": "petorb-oral-detector",
    "version": "2026-09-21"
  },
  "latency_ms": 184
}
```

## 4. 检测框坐标约定

`bbox` 必须基于**服务实际收到的原始 JPEG 像素坐标系**：

- 左上角为 `(0, 0)`；
- `x` 向右增大；
- `y` 向下增大；
- `x1, y1` 为左上角；
- `x2, y2` 为右下角；
- 坐标使用整数像素；
- 必须满足：
  - `0 <= x1 < x2 <= image.width`
  - `0 <= y1 < y2 <= image.height`

检测服务内部可以 resize / letterbox，但返回前必须映射回上传 JPEG 的原始尺寸。PetOrb 前端将直接按照这个坐标系叠框。

## 5. 字段约定

### `label`

- 类型：string；
- 必须使用稳定的 `snake_case` 标识；
- 不要把中文展示文案作为机器字段；
- 类别集合由模型团队维护，但一旦联调后不要随意改名。

示例：

```text
tartar_suspected
gingiva_redness
tooth_missing
oral_valid
```

### `confidence`

- 类型：number；
- 范围：`0.0 ~ 1.0`；
- 不要返回百分数 87 或字符串 `"87%"`。

### `detections`

没有目标时仍然返回 `200 OK`：

```json
{
  "request_id": "...",
  "image": {
    "width": 1280,
    "height": 720
  },
  "detections": [],
  "model": {
    "name": "petorb-oral-detector",
    "version": "2026-09-21"
  },
  "latency_ms": 153
}
```

`detections: []` 表示“本图没有检测到目标”，不是接口错误。

## 6. 错误响应

所有错误使用统一结构：

```json
{
  "error": {
    "code": "INVALID_IMAGE",
    "message": "image cannot be decoded"
  }
}
```

推荐状态码：

| HTTP | `error.code` | 场景 |
| ---: | --- | --- |
| 400 | `INVALID_IMAGE` | 文件为空、图片损坏、无法解码 |
| 413 | `IMAGE_TOO_LARGE` | 超过约定大小 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | 不是 JPEG |
| 500 | `INFERENCE_ERROR` | 模型推理内部错误 |
| 503 | `MODEL_NOT_READY` | 模型尚未加载完成 |

PetOrb 不要求模型服务提供 Mock 或假结果；接口异常会被真实记录为 PetOrb 会话失败。

## 7. PetOrb 与模型服务的职责边界

### 模型服务负责

- 接收 JPEG；
- 执行检测；
- 返回原图尺寸；
- 返回检测框；
- 返回稳定类别；
- 返回置信度。

### PetOrb 负责

- Camera Bridge 取图；
- 发送请求；
- 重试由 PetOrb 显式触发；
- 多张图片结果聚合；
- 检测框绘制；
- 风险等级与总体判断；
- 是否建议进一步人工检查/就医；
- 非诊断性护理提示；
- 会话状态与数据保存。

## 8. 联调最小验收

模型服务交给 PetOrb 前，只需要通过以下 4 个请求：

1. 一张正常 JPEG 返回 `200` 且包含至少一个合法 bbox；
2. 一张无目标 JPEG 返回 `200` + `detections: []`；
3. 一张损坏 JPEG 返回 `400 INVALID_IMAGE`；
4. 返回的 bbox 按原图尺寸绘制后与目标位置一致。

做到这四点即可开始正式联调。
