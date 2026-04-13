#!/usr/bin/env bash
# 운영 배포 (Linux/macOS). SSH config Host 별칭 besma-prod 필요.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE="${DIR}/remote_prod_deploy.sh"
if [[ ! -f "${REMOTE}" ]]; then
  echo "[deploy_prod.sh] ERROR: missing ${REMOTE}" >&2
  exit 1
fi
echo "[deploy_prod.sh] $(date -u +"%Y-%m-%dT%H:%M:%SZ") starting — ssh besma-prod"
ssh besma-prod "bash -s" < "${REMOTE}"
echo "[deploy_prod.sh] $(date -u +"%Y-%m-%dT%H:%M:%SZ") done"
