#!/usr/bin/env bash
# backend venv에서 app.main import가 되는지 확인 (routes/service 누락 조기 검출).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}/backend"
export ENV="${ENV:-prod}"
PY="${ROOT}/backend/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  echo "ERROR: venv python 없음: ${PY}" >&2
  exit 1
fi
"${PY}" -c "from app.main import app; print('verify_backend_import: OK')"
