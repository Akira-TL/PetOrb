#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/demo.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${NEXT_PUBLIC_API_URL:=http://127.0.0.1:8010}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[PetOrb] missing command: $1" >&2
    exit 1
  }
}

need uv
need corepack
need java

echo "[PetOrb] syncing FastAPI dependencies"
(
  cd "$ROOT/apps/server"
  uv sync
)

echo "[PetOrb] installing Web dependencies"
(
  cd "$ROOT/apps/web"
  corepack pnpm install --frozen-lockfile
)

echo "[PetOrb] building Web for API $NEXT_PUBLIC_API_URL"
(
  cd "$ROOT/apps/web"
  NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" corepack pnpm build
)

echo "[PetOrb] building Android Camera Bridge APK"
(
  cd "$ROOT/apps/android-camera-bridge"
  ./gradlew assembleDebug
)

cat <<OUT

[PetOrb] build complete
  Web:     apps/web/.next/
  Android: apps/android-camera-bridge/app/build/outputs/apk/debug/app-debug.apk

No test suite was executed by this build command.
OUT
