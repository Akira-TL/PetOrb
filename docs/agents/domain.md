# Domain Docs

本仓库采用 single-context。

## Before exploring, read these

- 根目录 `CONTEXT.md`（存在时）。
- 与当前工作相关的 `docs/adr/` 决策记录（存在时）。

这些文件尚不存在时直接继续，不把“先创建领域文档”当成开发前置条件；需要正式确定领域术语或架构决策时，由 `domain-modeling` 等对应 Skill 按需创建。

## ADR convention

当前仓库没有既有 ADR 约定，因此使用 Matt fallback：

- 目录：`docs/adr/`
- 命名：`NNNN-slug.md`
- 格式：使用 `domain-modeling/ADR-FORMAT.md`

## Vocabulary

Issue、测试、模块与文档中涉及领域概念时，以 `CONTEXT.md` 中已经定义的词汇为准。出现未定义概念时，先判断是否只是同义词漂移；确属新的领域概念，再交给领域建模流程处理。

## ADR conflicts

任何实现或设计若与既有 ADR 冲突，必须显式指出冲突并说明是否需要重新打开该决策，而不是静默覆盖。
