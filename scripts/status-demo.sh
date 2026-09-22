#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/demo.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${PETORB_DETECTOR_URL:=http://127.0.0.1:9000}"
: "${PETORB_API_PORT:=8010}"
: "${PETORB_WEB_PORT:=3000}"
: "${PETORB_BRIDGE_SERVER_URL:=http://192.168.137.1:8010}"

probe() {
  local name="$1"
  local url="$2"
  local expected="$3"
  local code
  code=$(curl -sS --max-time 2 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)
  if [[ "$code" =~ $expected ]]; then
    printf 'OK    %-12s %s (HTTP %s)\n' "$name" "$url" "$code"
  else
    printf 'DOWN  %-12s %s (HTTP %s)\n' "$name" "$url" "${code:-000}"
  fi
}

probe "FastAPI" "http://127.0.0.1:${PETORB_API_PORT}/health" '^200$'
probe "Web" "http://127.0.0.1:${PETORB_WEB_PORT}/" '^200$'
# Detector contract does not define a health endpoint; any HTTP response proves the process is reachable.
probe "Detector" "${PETORB_DETECTOR_URL%/}/v1/detect" '^[1-5][0-9][0-9]$'
printf 'INFO  %-12s %s\n' "Bridge URL" "$PETORB_BRIDGE_SERVER_URL"
