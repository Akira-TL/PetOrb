# PetOrb Local Detector

本服务把导入代码包中的 `YOLO11m-OBB` 权重接成 PetOrb 当前实时架构需要的本地 HTTP API。

默认模型：

```text
reference/petorb_3070_deploy/weights/best.pt
```

API：

```text
GET  /health
POST /v1/detect
```

输出类别：`gingi` / `sarro`，OBB 使用 `bbox.x1,y1 ... x4,y4`。

## Windows / RTX 3070 推荐安装

先创建环境，并按现场 CUDA 环境安装 PyTorch。例如 CUDA 12.1：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
python -m pip install -r apps\detector\requirements.txt
```

启动：

```powershell
python -m uvicorn apps.detector.petorb_detector.main:app --host 127.0.0.1 --port 9000
```

如果从 `apps/detector` 目录启动：

```powershell
python -m uvicorn petorb_detector.main:app --host 127.0.0.1 --port 9000
```

环境变量见 `.env.example`。默认 `conf=0.15`、`imgsz=640`、`device=0`，并启用原包中的 GO 3S 有效圆形区域裁剪逻辑，OBB 坐标会映射回原始 JPEG。
