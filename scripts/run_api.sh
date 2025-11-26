#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDS_DIR="${ROOT_DIR}/var/pids"
API_PID_FILE="${PIDS_DIR}/api_server.pid"

mkdir -p "${PIDS_DIR}"

echo "[run_api] 프로젝트 루트: ${ROOT_DIR}"

if command -v uv >/dev/null 2>&1; then
  UV_CMD="uv run --"
else
  UV_CMD=""
fi

if [ -f "${API_PID_FILE}" ] && kill -0 "$(cat "${API_PID_FILE}")" 2>/dev/null; then
  echo "[run_api] API 서버가 이미 실행 중입니다 (PID $(cat "${API_PID_FILE}"))."
  exit 0
fi

echo "[run_api] API 서버를 시작합니다 (port 8000)..."
(cd "${ROOT_DIR}" && ${UV_CMD} uvicorn api.main:app --reload --port 8000) &
echo $! >"${API_PID_FILE}"
echo "[run_api] API PID: $(cat "${API_PID_FILE}")"

