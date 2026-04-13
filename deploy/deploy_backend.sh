#!/usr/bin/env bash
# BESMA 백엔드 반자동 배포 (저장소 루트 또는 deploy/에서 실행 가능)
#
# 사용:
#   ./deploy/deploy_backend.sh
#   RUN_MIGRATIONS=1 ./deploy/deploy_backend.sh   # Alembic upgrade head 실행 후 재시작
#
# 필요: git, curl, sudo(systemctl), 활성화된 besma-backend.service
#
# 환경변수(선택):
#   BESMA_RESTART_SLEEP — 재시작 후 첫 대기 초 (기본 6)
#   BESMA_HEALTH_RETRIES — 헬스 curl 재시도 횟수 (기본 20)
#   BESMA_HEALTH_RETRY_SLEEP — 재시도 간격 초 (기본 2)
#   BESMA_VERIFY_OPENAPI_RISK_OVERVIEW=1 — 헬스 성공 후 openapi.json에 /dashboard/risk-db-overview 포함 여부 확인(없으면 경고만)

set -euo pipefail

PROJECT_ROOT="${BESMA_PROJECT_ROOT:-/home/ubuntu/besma-rev}"
BACKEND_DIR="${PROJECT_ROOT}/backend"
VENV_PY="${BACKEND_DIR}/.venv/bin/python"
HEALTH_URL="${BESMA_HEALTH_URL:-http://127.0.0.1:8001/health}"
RESTART_SLEEP="${BESMA_RESTART_SLEEP:-6}"
HEALTH_RETRIES="${BESMA_HEALTH_RETRIES:-20}"
HEALTH_RETRY_SLEEP="${BESMA_HEALTH_RETRY_SLEEP:-2}"
NGINX_UPLOAD_LIMIT="${BESMA_NGINX_CLIENT_MAX_BODY_SIZE:-20m}"

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

ensure_nginx_upload_limit() {
  if [[ ! -d /etc/nginx/conf.d ]]; then
    echo "[deploy] skip nginx upload limit (conf.d not found)"
    return
  fi

  local conf_path="/etc/nginx/conf.d/besma-client-max-body-size.conf"
  local desired="client_max_body_size ${NGINX_UPLOAD_LIMIT};"

  echo "[deploy] ensure nginx upload limit: ${desired}"
  printf '%s\n' "${desired}" | sudo tee "${conf_path}" >/dev/null
  sudo nginx -t
  sudo systemctl reload nginx
}

cd "${BACKEND_DIR}"

echo "[deploy] install backend dependencies"
"${VENV_PY}" -m pip install -r requirements.txt

# systemctl 재시작 전에 ImportError를 잡는다 (routes만 올라가고 service 누락 등).
echo "[deploy] verify import app.main (ENV=prod; skip with BESMA_SKIP_IMPORT_VERIFY=1)"
if [[ "${BESMA_SKIP_IMPORT_VERIFY:-0}" != "1" ]]; then
  if ! (cd "${BACKEND_DIR}" && ENV=prod "${VENV_PY}" -c "from app.main import app"); then
    echo "[deploy] ERROR: app.main import failed — uvicorn은 즉시 종료됩니다. 코드 수정 후 재배포하세요." >&2
    exit 1
  fi
fi

# DB 마이그레이션: 기본 비활성. 운영에서 필요할 때만 RUN_MIGRATIONS=1
if [[ "${RUN_MIGRATIONS:-0}" == "1" ]]; then
  echo "[deploy] alembic upgrade head"
  "${BACKEND_DIR}/.venv/bin/alembic" upgrade head
else
  echo "[deploy] skip alembic (set RUN_MIGRATIONS=1 to run)"
fi

ensure_nginx_upload_limit

echo "[deploy] systemctl restart besma-backend (sudo)"
sudo systemctl restart besma-backend

echo "[deploy] wait ${RESTART_SLEEP}s then health check: ${HEALTH_URL} (up to ${HEALTH_RETRIES} attempts, ${HEALTH_RETRY_SLEEP}s apart)"
sleep "${RESTART_SLEEP}"

health_ok=0
for ((i = 1; i <= HEALTH_RETRIES; i++)); do
  if curl -fsS --max-time 12 "${HEALTH_URL}" 2>/dev/null | grep -q '"status"'; then
    health_ok=1
    break
  fi
  echo "[deploy] health attempt ${i}/${HEALTH_RETRIES} not ready yet, sleep ${HEALTH_RETRY_SLEEP}s..."
  sleep "${HEALTH_RETRY_SLEEP}"
done

if [[ "${health_ok}" -ne 1 ]]; then
  echo "[deploy] ERROR: health check failed after ${HEALTH_RETRIES} attempts (expected JSON with status)" >&2
  echo "[deploy] systemctl status besma-backend:" >&2
  sudo systemctl status besma-backend --no-pager -l || true
  echo "[deploy] hint: journalctl -u besma-backend -n 80 --no-pager" >&2
  exit 1
fi

echo "[deploy] OK: besma-backend is up"

if [[ "${BESMA_VERIFY_OPENAPI_RISK_OVERVIEW:-0}" == "1" ]]; then
  OPENAPI_URL="${HEALTH_URL%/health}/openapi.json"
  echo "[deploy] verify openapi lists GET /dashboard/risk-db-overview (${OPENAPI_URL})"
  if curl -fsS --max-time 20 "${OPENAPI_URL}" 2>/dev/null | grep -q '"/dashboard/risk-db-overview"'; then
    echo "[deploy] OK: openapi includes risk-db-overview"
  else
    echo "[deploy] WARN: openapi에 /dashboard/risk-db-overview 없음 — 백엔드가 프론트보다 구버전일 수 있습니다." >&2
  fi
fi
