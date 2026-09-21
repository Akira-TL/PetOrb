# Issue tracker: GitHub

本仓库的需求、Spec 与 Ticket 统一存放在 GitHub Issues，默认通过 `gh` CLI 操作。

## Conventions

- 创建 Issue：`gh issue create --title "..." --body "..."`；多行正文使用 heredoc。
- 读取 Issue：`gh issue view <number> --comments`，同时读取 labels。
- 列出 Issue：`gh issue list --state open --json number,title,body,labels,comments`，按需要增加 `--label` / `--state` 过滤。
- 评论：`gh issue comment <number> --body "..."`。
- 增删标签：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`。
- 列出标签：`gh label list --limit 1000 --json name --jq '.[].name'`。
- 仅创建缺失标签：`gh label create "<name>"`；初始化阶段不使用 `--force`，已有标签保持原颜色和描述。
- 关闭 Issue：`gh issue close <number> --comment "..."`。

仓库由当前 Git remote 推断，通常无需显式传 `--repo`。

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Workflow integration

- Skill 要求“publish to the issue tracker”时，创建 GitHub Issue。
- Skill 要求“fetch the relevant ticket”时，执行 `gh issue view <number> --comments`。
- 阻塞关系优先使用 GitHub 原生 issue dependencies；CLI 不支持时再使用已认证 `gh api` 的 dependency endpoint。
- Worker claim 默认使用 `gh issue edit <n> --add-assignee @me` 提供 tracker 可见性；若并行协调 Skill 定义更强 claim 协议，以该协议为准。
- 普通实现 Ticket 只有在所有 Acceptance Criteria 都有最终实现与验证证据时才能关闭。
- Wayfinder map / child ticket 使用 `docs/agents/triage-labels.md` 中对应的 `wayfinder:*` 标签。
