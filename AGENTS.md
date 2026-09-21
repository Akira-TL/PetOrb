# PetOrb Agent Instructions

PetOrb 是影石智能影像挑战赛项目。软件工程任务统一先进入 `ask-akira`；涉及比赛截止时间、Demo、评审或现场交付时，由 `ask-akira` 按其规则选择 Competition 执行策略。专业工程方法继续由 Matt canonical Skills 负责，不在本文件复制流程正文。

项目文档默认使用中文，正式工程文档放在 `docs/`。项目级 Agent 指令只维护本文件，不建立重复的执行器专属规则副本。

## Agent skills

### Issue tracker

需求、Spec、Ticket 与工作状态统一记录在 GitHub Issues。具体操作见 `docs/agents/issue-tracker.md`。

### Workflow roles

Matt 工作流使用 canonical workflow role 作为 GitHub 标签值。映射见 `docs/agents/triage-labels.md`。

### Domain docs

本仓库采用 single-context；领域上下文使用根目录 `CONTEXT.md`，ADR 默认位于 `docs/adr/`。消费规则见 `docs/agents/domain.md`。
