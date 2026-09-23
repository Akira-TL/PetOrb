#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/apps/detector"
exec python -m uvicorn petorb_detector.main:app --host "${PETORB_DETECTOR_HOST:-127.0.0.1}" --port "${PETORB_DETECTOR_PORT:-9000}"
