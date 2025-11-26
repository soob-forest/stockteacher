#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDS_DIR="${ROOT_DIR}/var/pids"
API_PID_FILE="${PIDS_DIR}/api_server.pid"

if [ ! -f "${API_PID_FILE}" ]; then
  echo "[stop_api] API PID 파일이 없습니다 (${API_PID_FILE}). 건너뜁니다."
  exit 0
fi

pid="$(cat "${API_PID_FILE}")"

if ! kill -0 "${pid}" 2>/dev/null; then
  echo "[stop_api] API 프로세스가 이미 종료된 것 같습니다 (PID ${pid}). PID 파일을 삭제합니다."
  rm -f "${API_PID_FILE}"
  exit 0
fi

echo "[stop_api] API 서버를 종료합니다 (PID ${pid})..."
kill "${pid}" || true

sleep 1
if kill -0 "${pid}" 2>/dev/null; then
  echo "[stop_api] API가 아직 살아 있어 SIGKILL을 보냅니다."
  kill -9 "${pid}" || true
fi

rm -f "${API_PID_FILE}"
echo "[stop_api] API 서버 종료 완료."

