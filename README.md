## BESMA 로컬 MVP

안전보건 문서 취합 · 제출 · 승인/반려 · 의견청취관리대장을 로컬 환경에서 빠르게 검증하기 위한 MVP 프로젝트입니다.

### 1. 폴더 구조

- `backend`: FastAPI 기반 API 서버
- `frontend`: Vue 3 + TypeScript + Vite 기반 Admin UI
- `database`: SQLite DB (`besma.db`)
- `storage`: 업로드 문서/이미지 로컬 저장소
- `scripts`: 개발 실행 스크립트
- `docs`: IA 및 MVP/아키텍처 문서

### 2. 요구 사항

- Python 3.12+ (권장)
- Node.js 18+

### 3. 백엔드 설치 및 실행

```bash
cd backend
.venv\Scripts\activate
```

Python 3.12로 가상환경을 만들고 싶으면(권장), 아래처럼 실행합니다.

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# DB 및 시드 데이터 생성
python -m app.seed.seed_data

# 서버 실행
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### 4. 프론트엔드 설치 및 실행

```bash
cd frontend
npm install
npm run dev
```

### 5. 통합 실행 (Windows)

```bash
scripts\dev_start.bat
```

### 6. 샘플 계정

**새로 `python -m app.seed.seed_data`로 만든 DB** 기준으로, 아래 계정의 초기 비밀번호는 **P@ssw0rd!** 입니다.

- HQ 안전 관리자
  - `hqsafe1`
  - `hqsafe2`
- 현장 관리자
  - `site01`
  - `site02`
- 본사 타부서
  - `hqother1`

> **기존 `database/besma.db`를 그대로 쓰는 경우:** `seed_data`는 이미 있는 사용자의 비밀번호 해시를 바꾸지 않습니다. 예전에 `create_demo_login_users.py` 등으로 넣은 계정이 있으면 비밀번호가 다를 수 있습니다. 현장 데모 전에는 **DB 백업 후 DB 삭제·재시드** 또는 알려진 비밀번호로 로그인해 확인하세요.

### 6b. API 주소(프론트 ↔ 백엔드)

- 로컬에서 `scripts/start_backend.bat` 또는 README대로 백엔드를 **8001**에 띄웁니다.
- `VITE_API_BASE_URL`을 쓰지 않을 때 프론트는 같은 호스트의 **8001**로 API를 호출합니다(구버전 8000 고정 불일치는 제거됨).
- 운영·스테이징은 `frontend` 빌드 시 `VITE_API_BASE_URL`(예: `https://api.besma.co.kr`)을 반드시 설정하세요.

### 7. 주요 기능 (현재 구현 상태)

- 로그인 / JWT 인증
- `HQ_SAFE` / `SITE` / `HQ_OTHER` UI 타입 분기
- 문서 등록 · 임시저장 · 제출 · 승인 · 반려 · 재제출
- 승인/반려 이력 조회
- 전사/현장 의견청취관리대장 조회 및 등록/조치
- 기본 대시보드 KPI

### 8. 문서취합 IA 정합 기준 (2026-03 갱신)

문서취합은 "운영 UI 복제"가 아니라 **구성 정의 확인서 IA** 기준으로 다음처럼 역할을 분리합니다.

- **HQ 문서취합 관제**
  - 현장별 문서취합 KPI (전체/미제출/검토중/반려/승인)
  - 문서취합 신호등(RED/YELLOW/GREEN)
  - 미결재 문서 목록, 승인/반려 이력
- **Site 문서취합 업로드**
  - 법적 서류 / 준공서류 섹션 분리
  - 검토 코멘트 확인 후 수정 업로드(재업로드) 흐름
  - 준공서류는 "준공 전 6개월 구간"에서만 활성

재사용 원칙:

- `D:\BESMA\lib\safety-document-config.ts`의 주기/카테고리/정렬 개념 재사용
- 기존 BESMA 상태 배지, 업로드/이력 모달, KPI/테이블 패턴 재사용
- 단, 기능 범위/정보 구조 최종 기준은 확인서 IA 우선

