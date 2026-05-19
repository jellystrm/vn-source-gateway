#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${UI_PORT:-8765}"
BASE_URL="http://127.0.0.1:${PORT}"

if curl -fsS "${BASE_URL}/api/config" >/dev/null 2>&1; then
  echo "vn-source-gateway is already running: ${BASE_URL}"
  exit 0
fi

exec "${ROOT_DIR}/run"
