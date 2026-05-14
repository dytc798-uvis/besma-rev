# 운영 배포 런북 (프론트 + 백엔드)

**매 배포마다 이 문서 순서대로 실행하면 됩니다.**  
백엔드는 EC2(`api.besma.co.kr`) Git + `deploy_backend.sh`, 프론트는 **Vercel**입니다. `deploy_all.ps1`만으로 프론트가 올라가지 않습니다.

## 운영 연속성 우선

- **원칙:** 미반영·착각 배포로 HQ/현장 업무가 멈추는 비용이, 일반적인 Git 실수 방지 비용보다 크다. 에이전트·운영자 공통 상세는 **`docs/OPERATIONS_DEPLOY.md`** 의「운영 연속성 우선」절을 본다.
- **표준 흐름:** 변경 확인 → (필요 시) 안전 범위 커밋 → `git push origin main` → `deploy_all.ps1` → `deploy_frontend_vercel.ps1` → **푸시 SHA**, 스크립트 **`[deploy] Remote HEAD after pull:`**, **Vercel READY·프로덕션 별칭** 확인.
- **금지:** 위 검증 없이 “배포 완료”만 기술.
- **예외 플래그:** `-AllowDirtyWorkingTree`, `-SkipPush`, `-AllowSkipPushUnpushed`, `-SkipFrontendBuild`, `-RemoteGitCleanUntracked` — **기본은 깨끗한 트리 + push**; 표는 `OPERATIONS_DEPLOY.md` 참고.
- **pull 실패 시:** `deploy_all.ps1`는 원격 `ssh`가 실패하면 **0이 아닌 종료 코드**로 끝난다. 로그에 `[deploy] Remote HEAD after pull:` 가 없으면 배포가 끝까지 가지 않은 것이다.

---

## 0. 한 번만 확인할 것

| 항목 | 설명 |
|------|------|
| SSH 키 | 로컬에 PEM 존재. 기본 스크립트는 `%USERPROFILE%\Downloads\besma-key.pem` — 다른 경로면 **항상 `-SshKeyPath`로 지정** |
| Git | `main`에 반영할 커밋이 **원격(origin)에 push**된 상태 |
| Vercel | Volta로 설치된 Vercel CLI (`volta which vercel` 성공). 계정 로그인됨 (`whoami`로 확인) |
| Vercel 배포 인자 | 루트 `.env`에 `VERCEL_DEPLOY_SCOPE` / `VERCEL_DEPLOY_PROJECT` 저장 **또는** 아래 명령에 `-Scope` / `-Project`를 직접 적음 |

`.env` 예시는 저장소 루트 `/.env.example` 참고.

---

## 1. 백엔드 배포 (Windows PowerShell)

저장소 루트에서:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1 `
  -RepoRoot "C:\besma-rev\besma-rev_handoff" `
  -SshKeyPath "C:\besma-rev\besma-rev_handoff\.secrets\besma-key.pem" `
  -Branch main
```

- **`-RepoRoot` 생략 시:** `deploy` 폴더가 있는 저장소 루트가 기본값(스크립트 경로 기준). 예전처럼 다른 경로(`D:\besma-rev`)만 쓰던 실수를 줄인다.  
- 이미 `git push`를 했다면 **중복 push를 피하려면** `-SkipPush` 추가(로컬이 `origin/main`보다 앞서 있으면 **기본 중단** — push 후 재실행 또는 `-AllowSkipPushUnpushed`).  
- 로컬 프론트 빌드 검증을 건너뛰려면 `-SkipFrontendBuild` (배포 자체는 서버/Vercel에서 각각 빌드됨).  
- 미커밋이 있는데도 백엔드 스크립트를 강행하려면 `-AllowDirtyWorkingTree`(비권장: EC2에는 커밋된 히스토리만 반영됨).

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1 `
  -RepoRoot "C:\besma-rev\besma-rev_handoff" `
  -SshKeyPath "C:\besma-rev\besma-rev_handoff\.secrets\besma-key.pem" `
  -SkipPush
```

### 성공 판정 (백엔드)

- 로컬 스크립트가 **에러 없이 종료**(원격 `git pull`·헬스 체크 실패 시 `deploy_all.ps1`는 비정상 종료).
- 원격에서 `git pull --ff-only`가 **에러 없이** 끝남.
- 출력에 **`[deploy] Remote HEAD after pull:`** 및 `git log -1 --oneline` 한 줄(서버가 당긴 커밋 확인).
- 로그에 `[deploy] OK: besma-backend is up` 또는 스크립트 마지막 `curl .../health` 가 동작.
- 추가 확인(로컬에서):

```powershell
ssh -i "C:\besma-rev\besma-rev_handoff\.secrets\besma-key.pem" ubuntu@api.besma.co.kr "curl -fsS http://127.0.0.1:8001/health"
```

기대 응답: `{"status":"ok"}`

#### DB 마이그레이션만 적용할 때 (`pull`은 이미 성공)

`deploy_all.ps1`는 기본으로 원격에서 `RUN_MIGRATIONS=1 ./deploy/deploy_backend.sh`를 호출해 **`alembic upgrade head`가 포함**된다. `git pull`만 수동으로 끝낸 뒤 마이그레이션만 돌리려면 EC2에서:

```bash
cd /home/ubuntu/besma-rev/backend
.venv/bin/alembic upgrade head
sudo systemctl restart besma-backend
```

---

## 2. 원격 `git pull`이 막힐 때만 (서버 작업 트리가 지저분할 때)

증상: `Your local changes... would be overwritten` 또는 미추적 파일 때문에 `pull` / `merge` 중단.

**Alembic만 꼬인 경우(흔함):** `git status`에 `backend/alembic/versions/` 아래 **미추적 `.py`** 가 있으면, 원격에 없는 복사본이 `pull`과 충돌한다. 서버에서 해당 파일명을 기록한 뒤 `cp`로 백업하고 `rm` 한 파일만 지우거나, 아래 **선택**으로 `deploy_all.ps1 -RemoteGitCleanUntracked` 를 한 번 쓴다(해당 디렉터리의 **미추적만** 삭제).

**원칙:** 서버에서 코드는 **GitHub `origin/main`과 동일**하게 두고 배포한다. 업로드 파일(`storage/`), DB 백업(`database/` 등)은 건드리지 않는다.

PowerShell에서 아래 **한 블록**을 그대로 실행한다 (`SshKeyPath`만 본인 경로로).

```powershell
$remoteCmd = @"
set -euo pipefail
cd /home/ubuntu/besma-rev
git fetch origin
git reset --hard origin/main
git clean -fd backend/
chmod +x ./deploy/deploy_backend.sh
RUN_MIGRATIONS=1 ./deploy/deploy_backend.sh
curl -fsS http://127.0.0.1:8001/health
"@
$unix = ($remoteCmd -replace "`r`n", "`n" -replace "`r", "`n").TrimEnd()
$unix | ssh -i "C:\besma-rev\besma-rev_handoff\.secrets\besma-key.pem" ubuntu@api.besma.co.kr "bash -s"
```

- `git clean -fd backend/`는 **`backend/` 아래 미추적 파일만** 삭제한다. 서버에만 있던 임시 스크립트·중복 복사본 정리용.
- **서버 `backend/`에만 있고 Git에 없는 중요 파일**이 있다면 실행 전에 백업할 것.

정리 후에는 다시 **1절**의 `deploy_all.ps1`만으로도 다음 배포부터는 통과하는 경우가 많다.

---

## 3. 프론트엔드 배포 (Vercel, Windows PowerShell)

저장소 루트에서 (`.env`에 Vercel 변수가 있으면 `-Scope`/`-Project` 생략 가능):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1 `
  -RepoRoot "C:\besma-rev\besma-rev_handoff" `
  -Scope "sangik-jungs-projects" `
  -Project "besma-rev" `
  -RootDirectory "frontend"
```

### 성공 판정 (프론트)

- 로그에 `readyState":"READY"`, `target":"production"`.
- 프로덕션 별칭: `https://www.besma.co.kr` (Vercel 대시보드/CLI 출력 기준).

---

## 4. 매 배포 체크리스트 (복붙용)

1. [ ] `main`에 필요한 커밋 **push 완료**
2. [ ] `deploy_all.ps1` 실행 (`-SshKeyPath` / 필요 시 `-SkipPush`)
3. [ ] 1절 또는 SSH로 **`/health` = ok** 확인
4. [ ] (막히면) **2절** 원격 정리 후 다시 2~3
5. [ ] `deploy_frontend_vercel.ps1` 실행
6. [ ] 브라우저에서 `www.besma.co.kr` 주요 화면 확인

---

## 5. 관련 문서

| 문서 | 내용 |
|------|------|
| `DEPLOY_GUIDE.md` | 로컬 MVP + 운영 배포 개요 |
| `deploy/BACKEND_OPERATIONS.md` | systemd, 경로, health |
| `deploy/PRE_DEPLOY_CHECKLIST.md` | Push 전 코드/마이그레이션 점검 |
