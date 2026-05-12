# BESMA 로컬 MVP 배포 가이드

## 사전 요구사항

| 항목 | 최소 버전 | 확인 명령 |
|------|-----------|-----------|
| Python | 3.11+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |

> Windows 환경 기준. BAT 파일로 실행합니다.

---

## 1단계: 압축 해제

```
besma-rev.zip 해제 -> D:\besma-rev  (또는 원하는 폴더)
```

---

## 2단계: 환경변수 설정

루트의 `.env` 파일 확인/수정:

```env
BESMA_JWT_SECRET_KEY=change-me-to-secure-random
```

> 운영 환경에서는 반드시 안전한 랜덤 문자열로 교체하세요.

---

## 3단계: 백엔드 설정

```bat
cd backend
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### DB 마이그레이션 + 시드 데이터

```bat
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m app.seed.seed_data
```

> `run_backend.bat`을 실행하면 위 과정이 자동으로 수행됩니다.

---

## 4단계: 프론트엔드 설정

```bat
cd frontend
npm install
```

> `run_frontend.bat`을 실행하면 `node_modules`가 없을 경우 자동으로 `npm install`을 수행합니다.

---

## 5단계: 일괄 실행

### 방법 A: 일괄 실행 (권장)

```bat
run_local_mvp.bat
```

- Backend 창과 Frontend 창이 각각 열림
- 종료: `stop_local_mvp.bat` 실행

### 방법 B: 개별 실행

```bat
run_backend.bat     :: 별도 CMD 창에서
run_frontend.bat    :: 별도 CMD 창에서
```

---

## 6단계: 접속 확인

| 구분 | URL |
|------|-----|
| 프론트엔드 | http://127.0.0.1:5174 |
| 백엔드 Health | http://127.0.0.1:8001/health |
| Swagger 문서 | http://127.0.0.1:8001/docs |
| 외부 접속(같은 네트워크) | http://{PC-IP}:5174 |

---

## 테스트 계정

| 계정 | 비밀번호 | 역할 |
|------|----------|------|
| hqsafe1 | P@ssw0rd! | HQ 관리자 |
| site01 | P@ssw0rd! | 현장 관리자 |
| site02 | P@ssw0rd! | 현장 관리자 |
| worker01 | P@ssw0rd! | 근로자 |
| worker02 | P@ssw0rd! | 근로자 |

> 시드 데이터 기준. 실제 비밀번호는 `backend/app/seed/seed_data.py` 참조.

---

## 외부 네트워크 접속 (같은 Wi-Fi/LAN)

1. PC의 내부 IP 확인: `ipconfig` -> IPv4 주소 (예: 192.168.219.51)
2. `backend/app/config/settings.py`의 CORS 허용 목록에 해당 IP 추가 필요
3. 방화벽에서 8001, 5174 포트 허용 필요
4. 모바일 브라우저에서 `http://{PC-IP}:5174` 접속

---

## 주요 경로 (화면)

| 화면 | URL |
|------|-----|
| 로그인 | /login |
| HQ 문서 취합 현황 | /hq-safe/documents |
| 현장 내 현장 문서 | /site/documents |
| 현장관리자 모바일(일지·작업) | /site/mobile |
| 근로자 모바일 | /worker/mobile |
| 테스트 허브 (개발용) | /dev/hq-test, /dev/site-test, /dev/worker-test |

---

## 폴더 구조

```
besma-rev/
├── backend/          # FastAPI 백엔드
│   ├── app/          # 앱 코드
│   ├── alembic/      # DB 마이그레이션
│   ├── tests/        # 테스트
│   └── requirements.txt
├── frontend/         # Vue 3 프론트엔드
│   ├── src/          # 소스코드
│   ├── dist/         # 빌드 결과물 (프로덕션)
│   └── package.json
├── database/         # SQLite DB 파일
├── storage/          # 업로드 문서 저장소
├── docs/             # 문서
├── .env              # 환경변수
├── run_local_mvp.bat # 일괄 실행
├── run_backend.bat   # 백엔드 실행
├── run_frontend.bat  # 프론트엔드 실행
└── stop_local_mvp.bat # 일괄 종료
```

---

## 문제 해결

### 포트 충돌
```bat
netstat -ano | findstr :8001
netstat -ano | findstr :5174
taskkill /PID {PID번호} /F
```

### CORS 에러
`backend/app/config/settings.py`에서 접속 origin 추가:
```python
cors_origins = [
    "http://127.0.0.1:5174",
    "http://localhost:5174",
    "http://{접속IP}:5174",  # 추가
]
```

### DB 초기화 (처음부터 다시)
```bat
del database\besma.db
cd backend
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m app.seed.seed_data
```

---

## 운영 배포 (Windows) — **매번 이 순서**

**에이전트·세션 공통 요약:** `docs/OPERATIONS_DEPLOY.md` (저장소 루트에서 실행할 PowerShell 블록, 사전 조건)  
**한 문서에 순서대로 정리됨:** `deploy/PRODUCTION_DEPLOY_RUNBOOK.md`  
백엔드(EC2 + `deploy_backend.sh`)와 프론트(Vercel)는 **서로 다른 명령**이라, 둘 다 실행해야 화면·API가 함께 반영된다.

요약:

1. `main` push 후 `.\deploy\deploy_all.ps1` (키 경로가 다르면 `-SshKeyPath` 필수)
2. `.\deploy\deploy_frontend_vercel.ps1` (또는 런북의 `-Scope`/`-Project` 예시)

서버에서 `git pull`이 막히면(로컬 수정·미추적 파일) 런북 **2절** 절차로 원격 `backend/`만 정리한 뒤 다시 배포한다.

---

### 백엔드만 자동화할 때 (`deploy_all.ps1`)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1
```

- 기본값: RepoRoot `D:\besma-rev`, SSH 키 `%USERPROFILE%\Downloads\besma-key.pem`
- 동작: (선택) 프론트 빌드 검증 → `git push` → 서버에서 `git pull` + `deploy_backend.sh`
- 키가 다른 경로면: `-SshKeyPath "D:\besma-rev\besma-key.pem"` 등
- 상세: `deploy/PRODUCTION_DEPLOY_RUNBOOK.md`, `deploy/BACKEND_OPERATIONS.md`

### 프론트엔드(Vercel) 운영 배포

현재 `www.besma.co.kr` 프론트는 서버 정적파일이 아니라 **Vercel**에서 서비스된다.  
따라서 화면 변경은 백엔드 재기동만으로 반영되지 않고, **반드시** 아래 스크립트를 별도로 실행한다.

루트 `.env`에 아래 값을 저장해 두면 스크립트 인자를 생략할 수 있다:

```env
VERCEL_DEPLOY_SCOPE=sangik-jungs-projects
VERCEL_DEPLOY_PROJECT=besma-rev
VERCEL_DEPLOY_ROOT=frontend
VERCEL_DEPLOY_REPO_ROOT=D:\besma-rev
```

배포 명령:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1
```

인자를 명시하는 예시(`.env` 없을 때):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1 `
  -RepoRoot "D:\besma-rev" -Scope "sangik-jungs-projects" -Project "besma-rev" -RootDirectory "frontend"
```

최초 로그인까지 같이 할 때:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_frontend_vercel.ps1 -RunLogin
```

참고:

- 이 스크립트는 `npm --prefix frontend run build` 후 Vercel production 배포까지 수행한다.
- Windows에서 Vercel CLI가 비ASCII 호스트명 때문에 로그인 헤더 오류를 낼 수 있어, 스크립트 내부에서 `os.hostname()`을 ASCII 값으로 패치해 우회한다.
