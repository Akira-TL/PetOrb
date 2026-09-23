# PetOrb YOLO11m-OBB 检测包（3070）

只做本地检测，没有 HTTP API。

## 内容

| 路径 | 说明 |
|---|---|
| `weights/best.pt` | YOLO11m-OBB 最好权重 |
| `data/valid/` | 验证集 80 张图 + 标签 |
| `data/data.yaml` | val 配置 |
| `scripts/detect.py` | 跑检测，图上画框 |
| `scripts/run_val.py` | 算 P/R/mAP（可选） |
| `scripts/vis_val.py` | GT 绿框 + 预测橙框（可选） |

类别：`gingi` 牙龈炎，`sarro` 牙结石。

## 安装（3070 Laptop）

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
python -m pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## 跑检测

检测自带 val 图：

```powershell
python scripts\detect.py
```

检测一张自己的图：

```powershell
python scripts\detect.py D:\photo.jpg
```

结果图在 `runs/detect/`。

## 跑 val 指标（可选）

```powershell
python scripts\run_val.py
python scripts\vis_val.py
```

显存不够把 batch 改小：`python scripts\run_val.py --batch 4`
