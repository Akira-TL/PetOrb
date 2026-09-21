#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  jobs -pr | xargs -r kill
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT/apps/server"
  uv run uvicorn petorb_server.main:app --reload --host 0.0.0.0 --port 8010
) &

(
  cd "$ROOT/apps/web"
  corepack pnpm dev --hostname 0.0.0.0 --port 3000
) &

wait
