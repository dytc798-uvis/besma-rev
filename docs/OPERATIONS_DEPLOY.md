# BESMA 운영 반영(배포) — 에이전트·운영자 공통

> **목적:** 세션을 옮겨도 “어떻게 운영에 올리는지”를 한곳에서 찾을 수 있게 한다.  
> 사용자가 **「배포해」「운영 반영해」**라고 하면, 에이전트는 **본 문서 순서대로** PowerShell 명령을 실행한다(사전 승인이 필요한 경우만 확인).

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

- 이미 `git push`를 했다면: `-SkipPush` 추가.  
- 로컬 프론트 빌드 검증을 건너뛰려면: `-SkipFrontendBuild`.

**성공 판정:** 로그에 `[deploy] OK: besma-backend is up`, 원격 `curl …/health` → `{"status":"ok"}`.

### 2) 프론트엔드 (Vercel)

```powershell
cd C:\besma-rev\besma-rev_handoff
$env:Path = "C:\Program Files\Git\cmd;C:\Program Files\Volta;" + [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1 `
  -RepoRoot "C:\besma-rev\besma-rev_handoff"
```

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

- 사용자가 **운영 배포·배포해·프로덕션 반영** 등을 요청하면 **본 파일의 표준 절차**를 실행한다.  
- **백엔드만** 필요하면 1)만, **프론트만** 필요하면 2)만 실행할 수 있으나, 기본은 **둘 다** 시도한다.  
- 실패 시 로그·에러 메시지를 보고, 위 “사전 조건”과 런북 2절을 점검한다.
