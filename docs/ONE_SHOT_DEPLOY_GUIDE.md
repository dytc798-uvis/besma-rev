# BESMA 운영 배포 1회 가이드 (기능인정제 기준)

## 1) 운영 배포 순서
1. 저장소 루트에서 `main` 브랜치인지 확인.
2. 백엔드 배포 실행:
   - `powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1`
   - 깔끔한 배포를 위해 작업 트리를 깨끗하게 두고 실행.
   - 작업 트리 깨짐 시 임시로 `-AllowDirtyWorkingTree`만 허용하고, 실제 코드 반영은 커밋 뒤 `-SkipPush` 없이 실행해야 함.
3. 프론트 배포 실행:
   - `powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1`
   - 작업 트리 깨짐 시 `-AllowDirtyWorkingTree` 임시 허용 가능하나, 예측 가능한 운영 반영은 커밋 후 정돈된 트리에서 수행.
4. 프론트 최종 URL 확인: `https://www.besma.co.kr`
5. API 헬스 확인:
   - `https://api.besma.co.kr/health` 또는 원격 서버 `http://127.0.0.1:8001/health`

## 2) 이번 배포에서 사용한 명령
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1 -AllowDirtyWorkingTree`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1 -AllowDirtyWorkingTree -SkipFrontendBuild -SkipPush`

## 3) 이번 반영 체크
- 프론트: `Aliased: https://www.besma.co.kr` 상태 확인 완료 (`READY`).
- 백엔드: 스크립트 실행 및 원격 `git pull` 완료 후 `health` Up 체크 통과 (`OK: besma-backend is up`).
- 현재 작업 트리는 아직 깨끗하지 않으므로, 실제 운영 코드 반영은 필요한 변경분 커밋 후 `deploy_all.ps1` 정식 실행으로 마무리 권장.
