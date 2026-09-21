# PROTOTYPE — Rescue Mode Web 信息架构

三个完全不同的 Rescue Mode Web 结构，用于 Wayfinder 票“原型验证 Rescue Mode Web 演示信息架构”。

运行：

```bash
uv run python -m http.server 4173 --directory prototype/rescue-mode
```

访问：

- `http://localhost:4173/?variant=A` — 救助工作台
- `http://localhost:4173/?variant=B` — 单线演示流程
- `http://localhost:4173/?variant=C` — 风险分诊墙

这是一次性设计原型，不作为生产代码。
