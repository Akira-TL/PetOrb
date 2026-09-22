#!/usr/bin/env bash
set -euo pipefail

ADB_BIN="${ADB_BIN:-adb}"
ADB_SERVER_PORT="${ADB_SERVER_PORT:-5037}"
PETORB_API_PORT="${PETORB_API_PORT:-8010}"

command -v "$ADB_BIN" >/dev/null 2>&1 || {
  echo "[PetOrb] adb not found: $ADB_BIN" >&2
  exit 1
}

"$ADB_BIN" -P "$ADB_SERVER_PORT" devices
"$ADB_BIN" -P "$ADB_SERVER_PORT" reverse "tcp:${PETORB_API_PORT}" "tcp:${PETORB_API_PORT}"
echo "[PetOrb] USB reverse ready: Android 127.0.0.1:${PETORB_API_PORT} -> PC 127.0.0.1:${PETORB_API_PORT}"
