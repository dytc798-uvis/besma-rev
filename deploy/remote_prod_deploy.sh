#!/usr/bin/env bash
# 운영 서버에서 실행되는 단계 스크립트.
# 로컬에서: Get-Content ... | ssh besma-prod "bash -s"  또는 deploy/deploy_prod.ps1
#
# 전제: 저장소 경로 ~/besma-rev, backend venv 및 alembic 사용 가능.
# 민감정보·키는 포함하지 않는다.

set -euo pipefail

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[prod-deploy $(ts)] $*"; }
fail() {
  log "ERROR: $*"
  exit 1
}

trap 'log "ERROR: 명령 실패 (라인 ${LINENO}, exit $?)"' ERR

BESMA_ROOT="${BESMA_ROOT:-$HOME/besma-rev}"
BACKEND_DIR="${BESMA_ROOT}/backend"
VENV_ALEMBIC="${BACKEND_DIR}/.venv/bin/alembic"

log "STEP 1/7: cd ${BESMA_ROOT}"
cd "${BESMA_ROOT}" || fail "경로 없음: ${BESMA_ROOT}"

log "STEP 2/7: git pull --ff-only"
git pull --ff-only

log "STEP 3/7: cd ${BACKEND_DIR}"
cd "${BACKEND_DIR}" || fail "backend 경로 없음: ${BACKEND_DIR}"

if [[ ! -x "${VENV_ALEMBIC}" ]]; then
  fail "alembic 실행 파일 없음: ${VENV_ALEMBIC}"
fi

log "STEP 4/7: alembic current"
"${VENV_ALEMBIC}" current

log "STEP 5/7: alembic upgrade head"
"${VENV_ALEMBIC}" upgrade head

log "STEP 6/7: 저장소 루트에서 deploy_backend.sh (RUN_MIGRATIONS=0 — 마이그레이션은 위에서 이미 적용)"
cd "${BESMA_ROOT}" || fail "루트 복귀 실패: ${BESMA_ROOT}"
chmod +x ./deploy/deploy_backend.sh
RUN_MIGRATIONS=0 bash ./deploy/deploy_backend.sh

log "STEP 7/7: curl health (재확인)"
if ! curl -fsS --max-time 15 http://127.0.0.1:8001/health; then
  fail "health HTTP 요청 실패"
fi

log "완료: 운영 배포 단계가 모두 성공했습니다."
