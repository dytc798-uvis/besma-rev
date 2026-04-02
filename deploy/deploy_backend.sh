#!/usr/bin/env bash
# BESMA 백엔드 반자동 배포 (저장소 루트 또는 deploy/에서 실행 가능)
#
# 사용:
#   ./deploy/deploy_backend.sh
#   RUN_MIGRATIONS=1 ./deploy/deploy_backend.sh   # Alembic upgrade head 실행 후 재시작
#
# 필요: git, curl, sudo(systemctl), 활성화된 besma-backend.service

set -euo pipefail

PROJECT_ROOT="${BESMA_PROJECT_ROOT:-/home/ubuntu/besma-rev}"
BACKEND_DIR="${PROJECT_ROOT}/backend"
VENV_PY="${BACKEND_DIR}/.venv/bin/python"
HEALTH_URL="${BESMA_HEALTH_URL:-http://127.0.0.1:8001/health}"
RESTART_SLEEP="${BESMA_RESTART_SLEEP:-4}"

cd "${PROJECT_ROOT}"

echo "[deploy] git pull (${PROJECT_ROOT})"
git pull --ff-only

if [[ ! -d "${BACKEND_DIR}/.venv" ]]; then
  echo "[deploy] ERROR: venv not found: ${BACKEND_DIR}/.venv" >&2
  exit 1
fi

if [[ ! -x "${VENV_PY}" ]]; then
  echo "[deploy] ERROR: venv python missing or not executable: ${VENV_PY}" >&2
  exit 1
fi

cd "${BACKEND_DIR}"

# DB 마이그레이션: 기본 비활성. 운영에서 필요할 때만 RUN_MIGRATIONS=1
if [[ "${RUN_MIGRATIONS:-0}" == "1" ]]; then
  echo "[deploy] alembic upgrade head"
  "${BACKEND_DIR}/.venv/bin/alembic" upgrade head
else
  echo "[deploy] skip alembic (set RUN_MIGRATIONS=1 to run)"
fi

echo "[deploy] systemctl restart besma-backend (sudo)"
sudo systemctl restart besma-backend

echo "[deploy] wait ${RESTART_SLEEP}s then health check: ${HEALTH_URL}"
sleep "${RESTART_SLEEP}"

if ! curl -fsS --max-time 15 "${HEALTH_URL}" | grep -q '"status"'; then
  echo "[deploy] ERROR: health check failed (expected JSON with status)" >&2
  echo "[deploy] hint: journalctl -u besma-backend -n 80 --no-pager" >&2
  exit 1
fi

echo "[deploy] OK: besma-backend is up"
