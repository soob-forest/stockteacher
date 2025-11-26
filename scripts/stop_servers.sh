#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDS_DIR="${ROOT_DIR}/var/pids"
API_PID_FILE="${PIDS_DIR}/api_server.pid"
WEB_PID_FILE="${PIDS_DIR}/web_server.pid"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE_CMD="docker-compose"
else
  DOCKER_COMPOSE_CMD=""
fi

stop_one() {
  local name="$1"
  local pid_file="$2"

  if [ ! -f "${pid_file}" ]; then
    echo "[stop_servers] ${name} PID 파일이 없습니다 (${pid_file}). 건너뜁니다."
    return 0
  fi

  local pid
  pid="$(cat "${pid_file}")"

  if ! kill -0 "${pid}" 2>/dev/null; then
    echo "[stop_servers] ${name} 프로세스가 이미 종료된 것 같습니다 (PID ${pid}). PID 파일을 삭제합니다."
    rm -f "${pid_file}"
    return 0
  fi

  echo "[stop_servers] ${name} 서버를 종료합니다 (PID ${pid})..."
  kill "${pid}" || true

  sleep 1
  if kill -0 "${pid}" 2>/dev/null; then
    echo "[stop_servers] ${name}가 아직 살아 있어 SIGKILL을 보냅니다."
    kill -9 "${pid}" || true
  fi

  rm -f "${pid_file}"
  echo "[stop_servers] ${name} 서버 종료 완료."
}

stop_one "API" "${API_PID_FILE}"
stop_one "Web" "${WEB_PID_FILE}"

# if [ -n "${DOCKER_COMPOSE_CMD}" ]; then
#   echo "[stop_servers] Redis/Postgres 컨테이너를 중지합니다..."
#   (cd "${ROOT_DIR}" && ${DOCKER_COMPOSE_CMD} stop redis postgres) || true
# fi

echo "[stop_servers] 모든 서버 종료 요청을 마쳤습니다."
