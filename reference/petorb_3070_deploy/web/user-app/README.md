# PetOrb 用户端

用户端采用 React + Vite + Tailwind CSS 4 + MUI Icons。Python 检测服务在 `:8081` 提供 API 和构建后的页面。

在此目录运行：

```powershell
pnpm install
pnpm build
```

构建结果写入相邻的 `../user-dist/`，随后启动 `scripts/start_pc_detect_web.ps1` 即可访问 `http://127.0.0.1:8081/`。

开发时可运行 `pnpm dev`，Vite 会代理 `/api` 和 `/replay` 到正在运行的 `:8081` 服务。`?preview=1` 仅用于界面视觉核对，正常页面始终使用真实 API 数据。首页宠物插画位通过 `data-asset-slot="pet-illustration"` 标识，可在后续替换图片。
