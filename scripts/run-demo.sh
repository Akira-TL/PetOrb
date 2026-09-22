#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/demo.env"
RUNTIME_DIR="$ROOT/.data/runtime"
LOG_DIR="$ROOT/logs/demo"
PID_FILE="$RUNTIME_DIR/pids"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${PETORB_DETECTOR_URL:=http://127.0.0.1:9000}"
: "${PETORB_DETECTOR_TIMEOUT_SECONDS:=60}"
: "${PETORB_API_HOST:=0.0.0.0}"
: "${PETORB_API_PORT:=8010}"
: "${PETORB_WEB_HOST:=0.0.0.0}"
: "${PETORB_WEB_PORT:=3000}"
: "${NEXT_PUBLIC_API_URL:=http://127.0.0.1:8010}"
: "${PETORB_FFMPEG_BIN:=ffmpeg}"
: "${PETORB_STREAM_DISPLAY_FPS:=30}"
: "${PETORB_STREAM_INFERENCE_FPS:=10}"
: "${PETORB_STREAM_JPEG_QUALITY:=5}"
: "${PETORB_CAMERA_SOURCE_WS:=ws://127.0.0.1:8010/ws/camera/source}"
: "${PETORB_DATA_DIR:=$ROOT/.data/demo}"

mkdir -p "$RUNTIME_DIR" "$LOG_DIR" "$PETORB_DATA_DIR"

if ! command -v "$PETORB_FFMPEG_BIN" >/dev/null 2>&1; then
  echo "[PetOrb] FFmpeg not found: $PETORB_FFMPEG_BIN" >&2
  exit 1
fi

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn | awk '{print $4}' | grep -Eq "[:.]${port}$"
  else
    return 1
  fi
}

for port in "$PETORB_API_PORT" "$PETORB_WEB_PORT"; do
  if port_in_use "$port"; then
    echo "[PetOrb] port $port is already in use; stop the conflicting process first." >&2
    exit 1
  fi
done

if [[ ! -d "$ROOT/apps/web/.next" ]]; then
  echo "[PetOrb] Web production build missing. Run ./scripts/build-demo.sh first." >&2
  exit 1
fi

terminate_tree() {
  local pid="$1"
  [[ -z "$pid" ]] && return 0
  pkill -TERM -P "$pid" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true
}

cleanup() {
  set +e
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      terminate_tree "$pid"
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

: > "$PID_FILE"

(
  cd "$ROOT/apps/server"
  PETORB_DETECTOR_URL="$PETORB_DETECTOR_URL" \
  PETORB_DETECTOR_TIMEOUT_SECONDS="$PETORB_DETECTOR_TIMEOUT_SECONDS" \
  PETORB_DATA_DIR="$PETORB_DATA_DIR" \
  PETORB_FFMPEG_BIN="$PETORB_FFMPEG_BIN" \
  PETORB_STREAM_DISPLAY_FPS="$PETORB_STREAM_DISPLAY_FPS" \
  PETORB_STREAM_INFERENCE_FPS="$PETORB_STREAM_INFERENCE_FPS" \
  PETORB_STREAM_JPEG_QUALITY="$PETORB_STREAM_JPEG_QUALITY" \
  PETORB_CORS_ORIGINS="[\"http://127.0.0.1:${PETORB_WEB_PORT}\",\"http://localhost:${PETORB_WEB_PORT}\"]" \
  uv run uvicorn petorb_server.main:app \
    --host "$PETORB_API_HOST" \
    --port "$PETORB_API_PORT" \
    >>"$LOG_DIR/server.log" 2>&1
) &
server_pid=$!
echo "$server_pid" >> "$PID_FILE"

(
  cd "$ROOT/apps/web"
  corepack pnpm start --hostname "$PETORB_WEB_HOST" --port "$PETORB_WEB_PORT" \
    >>"$LOG_DIR/web.log" 2>&1
) &
web_pid=$!
echo "$web_pid" >> "$PID_FILE"

cat <<OUT
[PetOrb] demo services started
  Web:             http://127.0.0.1:${PETORB_WEB_PORT}
  FastAPI:         http://127.0.0.1:${PETORB_API_PORT}
  Camera source WS: ${PETORB_CAMERA_SOURCE_WS}
  Detector:        ${PETORB_DETECTOR_URL}
  Data:            ${PETORB_DATA_DIR}
  Logs:            ${LOG_DIR}

Press Ctrl+C to stop both services.
OUT

set +e
wait -n "$server_pid" "$web_pid"
status=$?
set -e
echo "[PetOrb] one demo process exited with status $status; shutting down the other process." >&2
exit "$status"
