# PetOrb Domain Context

## PetOrb

面向动物救助机构与养宠家庭的低干预宠物口腔影像采样与风险初筛系统。项目核心不是替代兽医诊断，而是通过 GO 3S 与专用采样结构稳定获得可供后续分析的口腔影像。

## Rescue Mode

PetOrb 在比赛 MVP 中优先实现的多动物照护模式。它面向救助机构、救助志愿者和寄养家庭，用于快速完成多只动物的采样并把有限的人力优先投入需要进一步人工复核的个体。

## AI 分析服务

由团队其他成员负责实现和维护的外部图像识别/分析能力。PetOrb 仓库只负责通过稳定接口提交输入、接收结构化结果并处理超时或失败，不实现模型训练、推理算法或模型内部流水线。
## Camera Bridge

PetOrb 比赛版中的极薄 Android 相机适配层。它只负责通过影石 Camera SDK 从 GO 3S 获取图像并将图像转发给 PetOrb 服务端，不承载 Rescue Mode 业务界面、AI 推理或结果展示。
## 采样会话（Sampling Session）

PetOrb 对一只动物的一次完整口腔采样与分析记录。比赛 MVP 同一时间只允许一个活动采样会话；Web 负责以 Animal ID 创建会话，Camera Bridge 上传的图像自动归入当前活动会话。
## 实时流架构（2026-09-22）

比赛主链已从“5 秒 JPEG 批次”切换为持续实时流：GO 3S PreviewStream H.264/H.265 由 Android Camera Bridge 原样通过 USB/ADB reverse WebSocket 转发到电脑；电脑 FastAPI 使用 FFmpeg 解码为约 30 FPS JPEG，全部帧用于 Web 实时显示，每 3 帧抽 1 帧送本机 Detector，目标约 10 FPS AI。AI 队列有界，满时丢旧帧，禁止积压实时延迟。
