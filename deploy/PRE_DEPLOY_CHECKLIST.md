# 배포 전 체크 (재발 방지)

## Push 전 (로컬)

1. **같은 PR/커밋에 묶기**: 라우트가 `from app.modules... import X` 하는 심볼은 `service` 등 **구현 파일까지 함께** 커밋했는지 확인.
2. **Alembic 체인**: 새 revision의 `down_revision`이 가리키는 파일이 **저장소에 존재**하는지 확인 (`KeyError: ...0031` 유형 방지).
3. **로컬 검증 (선택)**: `bash scripts/verify_backend_import.sh` 또는 PowerShell `.\scripts\verify_backend_import.ps1`

## 서버

1. **`deploy/deploy_backend.sh`를 서버에서 직접 수정하지 말 것.** 막히면 `git restore deploy/deploy_backend.sh` 후 `git pull`.
2. 배포 스크립트는 `pip install` 후·`systemctl restart` 전에 **`app.main` import 검증**을 수행한다. 긴급 스킵만 `BESMA_SKIP_IMPORT_VERIFY=1`.
3. `remote_prod_deploy.sh`는 **alembic 전**에 동일 import 검증을 수행한다.

## 성공 판정

- `[deploy] OK: besma-backend is up` 및 `/health` 응답.
