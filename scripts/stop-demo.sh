#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/.data/runtime/pids"

if [[ ! -f "$PID_FILE" ]]; then
  echo "[PetOrb] no demo PID file found."
  exit 0
fi

while read -r pid; do
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill "$pid" 2>/dev/null || true
    echo "[PetOrb] stopped process tree rooted at PID $pid"
  fi
done < "$PID_FILE"
rm -f "$PID_FILE"
