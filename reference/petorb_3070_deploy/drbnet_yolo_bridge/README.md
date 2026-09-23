# DRBNet 编码器 × PetOrb YOLO11m-OBB（结构草案）

这是一个**独立的新文件夹**，用于呈现两阶段网络方案。`F:\work\DRBnet` 和 PetOrb 原有 `scripts/`、`web/`、`weights/` 不需要改动；现有 8080/8081 服务也没有接入本方案。

## 两阶段连接关系

```text
阶段 A：去模糊预训练
模糊 RGB 图 [-1,1] → DRBNet_single 编码器 → 原 DRBNet 解码器 → 清晰图
                              │
                              └─ 保存 / 迁移编码器权重

阶段 B：旋转框检测
模糊 RGB 图 [-1,1] → DRBEncoder（保留预训练编码器）
                    → s4(128通道) + s8(256通道)
                    → DRBToYOLOPyramid
                    → P3/8、P4/16、P5/32（均512通道）
                    → PetOrb YOLO11m 的 FPN/PAN 颈部（原层11–22）
                    → OBB 检测头（原层23）
```

检测阶段不使用 DRBNet 的去模糊解码器，也不使用旧 YOLO 主干层 0–10。原 YOLO 权重中颈部和检测头的参数被保留；新特征适配层需要后续训练。

## 文件

| 路径 | 作用 |
|---|---|
| `third_party/drbnet/DRBNet.py` | 从 DRBNet 原项目逐字节复制的单图/双图网络源码；阶段 A 使用其中 `DRBNet_single` |
| `third_party/drbnet/LICENSE` | DRBNet 原项目的 GNU AGPLv3 许可证 |
| `models/drb_encoder.py` | 从 `DRBNet_single` 提取同名编码层，返回 s1/s2/s4/s8 特征 |
| `models/checkpoint_transfer.py` | 构造原去模糊网络，并仅迁移编码器参数 |
| `models/drb_yolo_obb.py` | DRB 特征适配器、原 YOLO 颈部与 OBB 头的连接结构 |
| `weights/drbnet_single.pth` | 从 DRBNet 已有的单图去模糊权重复制，尚未针对 PetOrb 数据重训 |
| `../weights/best.pt` | 精简交付包中的唯一一份 PetOrb YOLO11m-OBB 检测权重；构造 `BlurRobustOBB` 时传入此路径 |
| `source_reference/petorb/` | 检测脚本和类别配置的只读参考副本，不作为新网络的运行入口 |

## 当前边界

这份代码提供可实例化的 PyTorch 网络连接关系，**不是完成的联合模型**。没有训练数据管线、损失、训练循环、导出、推理后处理或线上服务集成。DRBNet 原权重只代表原去模糊任务的预训练；它对 PetOrb 模糊图检测的收益需要实验验证。新适配器是随机初始化的，直接用其输出判断牙龈炎或牙结石没有意义。

后续实现时应先确定模糊/清晰配对数据及 PetOrb OBB 标注，再训练适配器和检测颈部/头，并比较清晰图、模糊图上的 mAP。输入预处理也要统一：原 DRBNet 单图路径使用 RGB `[-1,1]`，现有 Ultralytics 检测路径的预处理不同。

## 来源与许可证

DRBNet 来源：`F:\work\DRBnet`，论文 *Learning to Deblur using Light Field Generated and Real Defocus Images*，原项目 GNU AGPLv3。复制和派生的 DRBNet 部分须遵守 `third_party/drbnet/LICENSE`；如需对外分发整个组合，请先核对许可证义务。PetOrb 参考代码和权重来源：`F:\work\petorb_3070_deploy`。两处原始文件均保持原样。
