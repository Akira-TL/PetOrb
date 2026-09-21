# Workflow Role Mapping

本文件把 Matt Engineering 使用的 workflow role 映射到本仓库 GitHub 标签。当前采用 canonical value，不做别名覆盖。

| Workflow role | GitHub label | Used by | Meaning |
| --- | --- | --- | --- |
| `ready-for-agent` | `ready-for-agent` | `to-tickets`, `triage` | 工作已充分定义，可由 Agent 执行 |
| `bug` | `bug` | `triage` | 缺陷 |
| `enhancement` | `enhancement` | `triage` | 新功能或改进 |
| `needs-triage` | `needs-triage` | `triage` | 尚待维护者分类与判断 |
| `needs-info` | `needs-info` | `triage` | 等待补充信息 |
| `ready-for-human` | `ready-for-human` | `triage` | 需要人工实现或人工判断 |
| `wontfix` | `wontfix` | `triage` | 决定不处理 |
| `wayfinder:map` | `wayfinder:map` | `wayfinder` | Wayfinder map issue |
| `wayfinder:research` | `wayfinder:research` | `wayfinder` | 研究型决策 ticket |
| `wayfinder:prototype` | `wayfinder:prototype` | `wayfinder` | 原型验证型决策 ticket |
| `wayfinder:grilling` | `wayfinder:grilling` | `wayfinder` | 需要人工 grilling 的决策 ticket |
| `wayfinder:task` | `wayfinder:task` | `wayfinder` | 用于解除决策阻塞的任务 |

下游 Skill 使用 workflow role 时，应先读取本表中的 tracker value；不要另造近义标签。
