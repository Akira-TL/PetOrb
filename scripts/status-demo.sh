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

probe_http() {
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

probe_detector() {
  local url="${PETORB_DETECTOR_URL%/}/health"
  local body
  body=$(curl -fsS --max-time 5 "$url" 2>/dev/null || true)
  if [[ "$body" == *'"status":"ok"'* || "$body" == *'"status": "ok"'* ]]; then
    printf 'OK    %-12s %s\n' "Detector" "$url"
  else
    printf 'DOWN  %-12s %s\n' "Detector" "$url"
  fi
}

probe_http "FastAPI" "http://127.0.0.1:${PETORB_API_PORT}/health" '^200$'
probe_http "Web" "http://127.0.0.1:${PETORB_WEB_PORT}/" '^200$'
probe_http "Stream API" "http://127.0.0.1:${PETORB_API_PORT}/api/stream/status" '^200$'
probe_detector
