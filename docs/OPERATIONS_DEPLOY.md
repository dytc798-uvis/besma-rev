# BESMA 운영 반영(배포) — 에이전트·운영자 공통

> **목적:** 세션을 옮겨도 “어떻게 운영에 올리는지”를 한곳에서 찾을 수 있게 한다.  
> 사용자가 **「배포해」「운영 반영해」**라고 하면, 에이전트는 **본 문서 순서대로** PowerShell 명령을 실행한다(사전 승인이 필요한 경우만 확인).

## 운영 연속성 우선 (재발 방지)

### 원칙

**미반영 배포·“성공” 착각**(로컬만 수정, push 누띄, 스크립트만 돌리고 검증 생략)으로 **HQ/현장 업무가 멈추는 비용**은, 일반적인 “커밋을 조심하자” 수준의 실수보다 훨씬 크다. 배포 절차에서는 **원격에 반영된 사실(SHA·스크립트 로그·헬스·Vercel 상태)** 을 근거로 말한다.

### 표준 운영자 흐름 (매번)

1. **변경 확인** — 반영하려는 수정이 맞는지, 제품 코드·설정 경로인지 본다.
2. **(필요 시) 안전 범위 커밋** — EC2는 **push된 커밋**만 당긴다. 미커밋 제품 변경이 있으면 스크립트가 기본으로 중단한다 → **의도된 변경만** 스테이징해 커밋한다.
3. **`git push origin main`** — `deploy_all.ps1`가 push를 포함하더라도, 운영자는 **원격에 올라간 커밋**이 무엇인지 알 수 있게 푸시 직후 SHA를 기준으로 한다(로컬 `HEAD`와 `origin/main` 일치 확인 권장).
4. **`deploy_all.ps1`** → **`deploy_frontend_vercel.ps1`** — 사용자가 “백엔드만” 등으로 한정하지 않는 한 **둘 다** 실행한다.
5. **반드시 확인 (말로 끝내지 않음)**  
   - **푸시된 SHA:** 로컬 `git rev-parse HEAD`와 원격 `git ls-remote origin refs/heads/main`(또는 사용 브랜치) 등으로 **포함 커밋**을 확인한다.  
   - **백엔드:** 출력 **`[deploy] Remote HEAD after pull:`** 및 `git log -1 --oneline` 한 줄, 필요 시 `/health` = `ok`.  
   - **프론트:** Vercel 출력 **`readyState":"READY"`**, 프로덕션 **별칭**(예: `https://www.besma.co.kr`).

### 금지

**“배포 완료”만** 말하고 **push 여부·포함 커밋·스크립트 성공 로그**를 확인하지 않는 것.

### 비밀·대용량 (그대로 제외)

개인키(`*.pem` 등), `.env` **실비밀**, `storage/` 등 **대용량·로컬 전용 데이터**는 **커밋·동반 업로드 금지**다. 이는 운영 연속성과 별개인 **보안·저장소 정책**이다.

### 배포 트리 위생 (커밋 전)

운영 배포에 실리는 것은 **`git push`된 제품 코드·마이그레이션·문서**뿐이다. 스테이징·커밋에서 **제외**할 것: SSH 키·자격 증명(`*.pem`, `.env` 실값, `besma-key.pem`), `storage/` 업로드·ingestion 산출물, `frontend/node_modules`·`node_modules.bak_*`, 로컬 스크린샷·핸드오프 아카이브(`handoff-besma/` 등) 중 배포와 무관한 바이너리, `docs/base`·`docs/field_qa_screenshots` 같은 **참고용 대용량** (제품 변경이 아니면 별도 PR). `deploy_all.ps1`는 미커밋이 있으면 기본 **중단**하므로, 반영할 수정만 골라 커밋한 뒤 push한다.

### 예외: 프리플라이트 플래그

**기본값 = 깨끗한 작업 트리 + 원격에 반영된 커밋.** 아래는 **예외**로만 쓴다(사유·상황을 기록할 것).

| 플래그 | 용도 |
|--------|------|
| `-AllowDirtyWorkingTree` | 미커밋이 있어도 스크립트 진행(EC2에 올라가는 것은 여전히 **push된 코드**). |
| `-SkipPush` | 이미 push함. 로컬이 `origin/main`보다 앞서 있으면 기본 실패. |
| `-AllowSkipPushUnpushed` | push 없이 진행 강제(위험; 런북·사유 명시 후만). |
| `-SkipFrontendBuild` | 로컬 프론트 빌드 검증만 생략. |
| `-RemoteGitCleanUntracked` | **EC2 전용.** `git pull` 직전에 `backend/alembic/versions/` 아래 **미추적 파일만** `git clean -fd`로 삭제한다. 서버에만 생긴 Alembic 복사본 등으로 pull이 막힐 때만, 백업·사유 기록 후 사용(기본값 꺼짐). |

**원격 `git pull` 실패 시:** `deploy_all.ps1`는 `ssh` 종료 코드를 검사해 **비정상 종료**로 끝난다(성공 착각 방지). pull이 통과한 뒤 DB 마이그레이션은 `deploy_backend.sh` 또는 수동 `alembic upgrade head`로 진행한다.

전체 단계·명령 예: 아래 **표준 배포 절차** 및 `deploy/PRODUCTION_DEPLOY_RUNBOOK.md`.

---

## 한 줄 요약

| 구분 | 대상 | 명령 |
|------|------|------|
| 백엔드 | EC2 `api.besma.co.kr` (Git pull + `deploy_backend.sh`) | `deploy\deploy_all.ps1` |
| 프론트 | Vercel `www.besma.co.kr` | `deploy\deploy_frontend_vercel.ps1` |

**둘 다** 실행해야 API 변경과 화면 변경이 함께 반영된다.

---

## 사전 조건 (Windows, 저장소 루트에서)

1. **워크스페이스**  
   실제 클론 루트(예: `C:\besma-rev\besma-rev_handoff`)에서 실행한다.  
   루트에 `frontend`, `backend`, `deploy` 폴더가 보여야 한다.

2. **Git**  
   PATH에 `git`이 잡혀 있어야 한다.  
   `main`에 올릴 커밋이 있으면 **먼저 push**한다 (`deploy_all.ps1`는 기본적으로 push 포함).  
   **로컬에만 있는 수정(미커밋)** 은 EC2 `git pull`로는 절대 반영되지 않는다. `deploy_all.ps1`는 기본적으로 **작업 트리가 깨끗하지 않으면 중단**한다(재발 방지). 우회 시 `-AllowDirtyWorkingTree`.

3. **SSH 키**  
   - 권장 위치: `.secrets\besma-key.pem`  
   - 루트 `.env`의 `BESMA_SSH_KEY_PATH` 또는 스크립트 기본 탐색 경로.  
   - OpenSSH 오류 `UNPROTECTED PRIVATE KEY FILE` 시, 키 파일 ACL을 **현재 사용자만 읽기**로 제한한다:

   ```powershell
   $key = "C:\besma-rev\besma-rev_handoff\.secrets\besma-key.pem"
   $u = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
   icacls $key /inheritance:r
   icacls $key /grant:r "${u}:(R)"
   ```

4. **Vercel CLI**  
   Volta 등으로 `vercel` 사용. 최초 1회 로그인:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1 -RunLogin
   ```

5. **루트 `.env` (Vercel 배포용)**  
   실제 경로에 맞게 `VERCEL_DEPLOY_REPO_ROOT`를 둔다. 예:

   ```env
   VERCEL_DEPLOY_SCOPE=sangik-jungs-projects
   VERCEL_DEPLOY_PROJECT=besma-rev
   VERCEL_DEPLOY_ROOT=frontend
   VERCEL_DEPLOY_REPO_ROOT=C:\besma-rev\besma-rev_handoff
   BESMA_SSH_KEY_PATH=C:\besma-rev\besma-rev_handoff\.secrets\besma-key.pem
   ```

---

## 표준 배포 절차 (사용자가 “배포”라고 했을 때)

저장소 루트에서 **순서대로** 실행한다.

### 1) 백엔드

```powershell
cd C:\besma-rev\besma-rev_handoff
$env:Path = "C:\Program Files\Git\cmd;C:\Program Files\Volta;" + [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1 `
  -RepoRoot "C:\besma-rev\besma-rev_handoff"
```

- `-RepoRoot`를 생략하면 **`deploy` 폴더가 들어 있는 저장소 루트**로 자동 설정된다(다른 드라이브 `D:\besma-rev`에 잘못 배포하는 실수 방지).  
- 이미 `git push`를 했다면: `-SkipPush` 추가(이때 **로컬이 origin보다 앞서 있으면 스크립트가 실패**한다; push 후 다시 실행하거나 `-AllowSkipPushUnpushed`로만 우회).  
- 로컬 프론트 빌드 검증을 건너뛰려면: `-SkipFrontendBuild`.  
- 작업 트리에 미커밋이 있어도 백엔드만 올리려면(비권장): `-AllowDirtyWorkingTree`.

**성공 판정:** 로그에 `[deploy] OK: besma-backend is up`, 원격 `curl …/health` → `{"status":"ok"}`. 로그에 **`[deploy] Remote HEAD after pull:`** 와 **커밋 한 줄**이 나오면 서버가 실제로 당긴 SHA를 확인할 수 있다.

**EC2 Alembic 미추적 파일로 `pull`이 막힐 때:** 서버에서 `git status`로 경로를 확인한 뒤, 해당 파일을 백업·삭제하거나 `deploy/PRODUCTION_DEPLOY_RUNBOOK.md` 「원격 git pull이 막힐 때」절을 따른다. 한 경로만 정리하려면 `deploy_all.ps1`에 **`-RemoteGitCleanUntracked`** 를 붙여 `backend/alembic/versions/` 아래 미추적만 제거한 뒤 재실행한다.

### 배포했는데 변경이 안 보일 때 (원인 패턴)

| 증상 | 흔한 원인 |
|------|-----------|
| API/백엔드만 예전 동작 | 수정이 **커밋·push 안 됨** 또는 `-SkipPush`인데 로컬이 origin보다 앞섬. EC2는 **원격 Git**만 당김. |
| 프론트만 예전 화면 | `deploy_frontend_vercel.ps1`를 **안 돌림**(백엔드 스크립트만 실행). 또는 Vercel **다른 프로젝트/스코프**로 링크됨. |
| 로컬에선 보이는데 운영엔 없음 | **미커밋 변경**만 로컬에 있음 → 백엔드는 반영 불가. 프론트는 디스크 업로드라 올라갈 수 있으나, 스크립트는 기본 **깨끗한 트리**를 요구한다. |
| 다른 PC의 클론이 배포됨 | 예전 기본값 `D:\besma-rev` 등 **다른 RepoRoot**로 스크립트 실행. 지금은 `-RepoRoot` 생략 시 스크립트 위치 기준으로 잡힌다. |

### 2) 프론트엔드 (Vercel)

```powershell
cd C:\besma-rev\besma-rev_handoff
$env:Path = "C:\Program Files\Git\cmd;C:\Program Files\Volta;" + [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1 `
  -RepoRoot "C:\besma-rev\besma-rev_handoff"
```

- 미커밋이 있으면 기본적으로 **중단**한다. 로컬만의 실험 배포가 필요하면 `-AllowDirtyWorkingTree`.

**성공 판정:** 출력에 `readyState":"READY"`, `Aliased: https://www.besma.co.kr` 유사 메시지.

---

## Git push가 거절될 때

`non-fast-forward`면 원격이 앞선 상태다.

```powershell
git fetch origin
git pull --rebase origin main
# 충돌 해결 후
git push origin main
```

그 다음 `deploy_all.ps1`를 다시 실행한다.

---

## 서버에서 `git pull`이 막힐 때

`deploy/PRODUCTION_DEPLOY_RUNBOOK.md` **2절** (원격 `backend/` 정리 + `deploy_backend.sh`)을 따른다.

---

## 관련 문서

| 문서 | 내용 |
|------|------|
| `deploy/PRODUCTION_DEPLOY_RUNBOOK.md` | 운영 런북 전체(백·프론트, 트러블슈팅) |
| `DEPLOY_GUIDE.md` | 로컬 MVP + 운영 배포 개요 |
| `deploy/PRE_DEPLOY_CHECKLIST.md` | 배포 전 체크 |

---

## 에이전트 동작 규칙 (요약)

- 사용자가 **운영 배포·배포해·프로덕션 반영** 등을 요청하면 **위「운영 연속성 우선」** 및 **표준 배포 절차**를 따른다(기본 묶음: Git 상태 확인 → 필요 시 안전 커밋·push → 두 스크립트 → **SHA·Remote HEAD·Vercel READY/별칭** 보고). 상세는 `.cursor/rules/besma-deploy-on-request.mdc`.  
- **백엔드만** 필요하면 1)만, **프론트만** 필요하면 2)만 실행할 수 있으나, 기본은 **둘 다** 시도한다.  
- 실패 시 로그·에러 메시지를 보고, 위 “사전 조건”과 런북 2절을 점검한다.
