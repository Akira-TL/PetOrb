# PetOrb

PetOrb 是面向影石智能影像挑战赛的低干预宠物口腔影像采样与风险初筛系统。

当前软件主链：

```text
GO 3S → Android Camera Bridge → FastAPI → external detector → Detection Workbench
```

## Detector contract

模型队友使用 `docs/api/ai-detector-contract.md` 作为 HTTP 联调协议。

## Development

### 1. Server

```bash
cd apps/server
uv sync --dev
cp .env.example .env
uv run uvicorn petorb_server.main:app --reload --host 0.0.0.0 --port 8010
```

### 2. Web

```bash
cd apps/web
corepack pnpm install
cp .env.example .env.local
corepack pnpm dev
```

打开 `http://localhost:3000`。

依赖安装完成后，也可以从仓库根目录同时启动：

```bash
./scripts/dev.sh
```

## Validation

```bash
cd apps/server && uv run pytest
cd apps/web && corepack pnpm lint && corepack pnpm build
```
