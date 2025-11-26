#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDS_DIR="${ROOT_DIR}/var/pids"
API_PID_FILE="${PIDS_DIR}/api_server.pid"
WEB_PID_FILE="${PIDS_DIR}/web_server.pid"

mkdir -p "${PIDS_DIR}"

echo "[run_servers] 프로젝트 루트: ${ROOT_DIR}"

if command -v uv >/dev/null 2>&1; then
  UV_CMD="uv run --"
else
  UV_CMD=""
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE_CMD="docker-compose"
else
  DOCKER_COMPOSE_CMD=""
fi

start_containers() {
  if [ -z "${DOCKER_COMPOSE_CMD}" ]; then
    echo "[run_servers] docker compose/docker-compose 명령을 찾지 못했습니다. Redis/Postgres는 수동으로 올려주세요." >&2
    return 0
  fi

  echo "[run_servers] Redis/Postgres 컨테이너를 시작합니다..."
  (cd "${ROOT_DIR}" && ${DOCKER_COMPOSE_CMD} up -d redis postgres)
}

start_api() {
  if [ -f "${API_PID_FILE}" ] && kill -0 "$(cat "${API_PID_FILE}")" 2>/dev/null; then
    echo "[run_servers] API 서버가 이미 실행 중입니다 (PID $(cat "${API_PID_FILE}"))."
  else
    echo "[run_servers] API 서버를 시작합니다 (port 8000)..."
    (cd "${ROOT_DIR}" && ${UV_CMD} uvicorn api.main:app --reload --port 8000) &
    echo $! >"${API_PID_FILE}"
    echo "[run_servers] API PID: $(cat "${API_PID_FILE}")"
  fi
}

start_web() {
  if [ -f "${WEB_PID_FILE}" ] && kill -0 "$(cat "${WEB_PID_FILE}")" 2>/dev/null; then
    echo "[run_servers] Web 서버가 이미 실행 중입니다 (PID $(cat "${WEB_PID_FILE}"))."
  else
    echo "[run_servers] Web 서버를 시작합니다 (Next.js dev on port 3000)..."
    (cd "${ROOT_DIR}/web" && npm run dev) &
    echo $! >"${WEB_PID_FILE}"
    echo "[run_servers] Web PID: $(cat "${WEB_PID_FILE}")"
  fi
}

start_containers
start_api
start_web

echo "[run_servers] API: http://127.0.0.1:8000/healthz"
echo "[run_servers] Web: http://127.0.0.1:3000"
