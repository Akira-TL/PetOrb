# PetOrb 外部检测模型 HTTP 接口协议

版本：v1.1（当前）

> 当前协议使用**每个目标四个角点**表达检测区域。旧 `bbox: {x1,y1,x2,y2}` 已废弃，不再兼容。

## 1. 目的

PetOrb 通过 HTTP 向团队外部图像检测服务提交**单张 JPEG**。检测服务只负责返回目标类别、置信度和目标区域的四个原图像素坐标点；风险聚合、就医建议、Web 展示与数据持久化全部由 PetOrb 服务端负责。

## 2. Endpoint

```http
POST /v1/detect
Content-Type: multipart/form-data
```

### Form 字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `image` | file | 是 | 单张 JPEG，`image/jpeg` |
| `request_id` | string | 否 | PetOrb 生成的请求 ID；若提供，响应必须原样返回 |

约定：

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
      "points": [
        {"x": 412, "y": 203},
        {"x": 690, "y": 210},
        {"x": 682, "y": 461},
        {"x": 405, "y": 450}
      ]
    },
    {
      "label": "gingiva_redness",
      "confidence": 0.78,
      "points": [
        {"x": 705, "y": 250},
        {"x": 1012, "y": 262},
        {"x": 998, "y": 486},
        {"x": 696, "y": 472}
      ]
    }
  ],
  "model": {
    "name": "petorb-oral-detector",
    "version": "2026-09-22"
  },
  "latency_ms": 184
}
```

## 4. 四点坐标约定

每个 detection 的 `points`：

- **必须恰好 4 个点**；
- 每个点格式为 `{"x": int, "y": int}`；
- 坐标基于**服务实际收到的原始 JPEG 像素坐标系**；
- 左上角为 `(0, 0)`；
- `x` 向右增大，`y` 向下增大；
- 四点沿目标边界**顺时针排列**；
- 起点任意，不要求第一个点一定是左上角；
- 四个点必须互不重复；
- 所有点必须满足：
  - `0 <= x <= image.width`
  - `0 <= y <= image.height`

例如一个倾斜目标：

```json
"points": [
  {"x": 412, "y": 203},
  {"x": 690, "y": 210},
  {"x": 682, "y": 461},
  {"x": 405, "y": 450}
]
```

Detector 内部可以 resize、letterbox、crop 或透视变换，但**返回前必须把四点映射回上传 JPEG 的原始尺寸**。PetOrb Web 会直接按这四个点绘制 SVG polygon。

## 5. 字段约定

### `label`

- 类型：string；
- 使用稳定的 `snake_case`；
- 不要把中文展示文案作为机器字段；
- 类别集合由模型团队维护，联调后不要随意改名。

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
- 不要返回百分数 `87`；
- 不要返回字符串 `"87%"`。

### `points`

- 类型：array；
- 长度固定为 `4`；
- 每个元素必须含整数 `x`、`y`；
- 不再接受 `bbox`。

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
    "version": "2026-09-22"
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

## 7. PetOrb 与模型服务职责边界

### 模型服务负责

- 接收 JPEG；
- 执行检测；
- 返回原图尺寸；
- 每个目标返回四个原图坐标点；
- 返回稳定类别；
- 返回置信度。

### PetOrb 负责

- Camera Bridge 取图；
- 发送请求；
- 多张图片结果聚合；
- 四点目标区域绘制；
- 证据帧选择；
- 风险等级与总体判断；
- 是否建议进一步人工检查/就医；
- 非诊断性护理提示；
- 会话状态与数据保存。

## 8. 联调最小验收

模型服务交给 PetOrb 前，只需要满足：

1. 正常 JPEG → `200`，至少一个 detection，且每个 detection 恰好 4 个合法点；
2. 无目标 JPEG → `200` + `detections: []`；
3. 损坏图片 → `400 INVALID_IMAGE`；
4. 四个点按原图坐标绘制后与目标区域一致；
5. 内部 resize / letterbox 后返回坐标仍已映射回原图。

做到以上即可开始正式联调。
