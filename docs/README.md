# BESMA docs 개요

이 폴더는 BESMA 로컬 MVP의 주요 기준 문서와 샘플 데이터를 포함한다.

## 1. 기준 문서

- `BESMA_SESSION_STATE.md`  
  - 현재 세션 기준 프로젝트, 최근 작업 이력, 열린 이슈, 다음 작업 계획을 기록하는 **동적 상태 문서**.
- `ai_collaboration_policy.md`  
  - Cursor / Codex / ChatGPT 등 AI 작업자 공통 운영 규정.
- `SESSION_START_REQUIRED.md`  
  - 새 세션 시작 시 반드시 먼저 읽어야 하는 진입 문서.

## 2. Site import 샘플 (`docs/sample/site_import/`)

### raw/
ERP에서 다운로드한 원본 데이터
- 절대 수정 금지
- 실제 site import 대상

### cleaned/
사람이 정제한 목표 형태
- Site 테이블에 저장되어야 하는 결과 기준

### 규칙

- `site_name` = 공사명
- 현장명은 사용하지 않음
- 공사기간 → `start_date` / `end_date` 분리
- 도급금액 → `project_amount`
- 숫자 필드는 숫자만 남김
- `'-'` 또는 공란 → `null`

이 샘플을 기준으로 site import 로직을 구현·검증한다.

## 3. Worker import 샘플 (`docs/sample/site_import/raw/employees_raw*.xlsx`, `daily_workers_raw.xls`)

Worker 인력 마스터 구축을 위한 ERP 원본 파일은 아래를 기준으로 사용한다.

- `employees_raw.xlsx`  
  - 정규직/사원 리스트 baseline 원본.
- `employees_raw_v1.xlsx` / `employees_raw_v2.xlsx`  
  - NEW / UPDATED diff 검증용 샘플.
- `daily_workers_raw.xls`  
  - 일용직 사원 리스트 원본.

backend 기준:
- Person / Employment / WorkerImportBatch / workers diff 기능은 이 샘플들을 기준으로 normalize/import/diff 를 수행하도록 구현되어야 한다.

## 4. 위험성평가 DB 샘플 (`docs/safetyRisk_DB.xlsx`)

위험요인/대책 자동추천의 원천 데이터는 엑셀 자체가 아니라 플랫폼 내부 표준 스키마를 기준으로 관리한다.

- 입력 원본: `docs/safetyRisk_DB.xlsx`
- 적재 스크립트: `backend/scripts/import_safety_risk_db.py`
- 적재 대상 테이블:
  - `risk_library_items`
  - `risk_library_item_revisions`
  - `risk_library_keywords`

### 적재/정규화 원칙

- 엑셀 구조를 그대로 복제하지 않는다.
- 플랫폼 표준 필드로 정규화한다.
  - `work_category`
  - `trade_type`
  - `risk_factor`
  - `risk_cause` (원본 분리 컬럼 미확정 시 기본값 처리)
  - `countermeasure`
  - `risk_f` / `risk_s` / `risk_r`
  - `keywords`
- 공란/병합셀은 컨텍스트 승계 규칙으로 처리한다.
- 자동추천은 키워드 exact-match 중심으로 동작한다.

### 실행 예시

- `cd backend`
- `.venv\Scripts\python.exe scripts\import_safety_risk_db.py`

## 5. 로컬 MVP 실행(BAT)

루트(`D:\besma-rev`)에서 아래 BAT를 사용하면 된다.

- `run_local_mvp.bat`
  - 백엔드: `http://127.0.0.1:8001`
  - 프론트엔드: `http://127.0.0.1:5174`
  - 두 프로세스를 별도 cmd 창(`BESMA Backend`, `BESMA Frontend`)으로 실행
- `stop_local_mvp.bat`
  - 위 두 창을 종료

## 6. 테스트 Persona 모드

로컬 테스트에서만 고정 로그인 + 페르소나 UI 분기를 사용하려면 아래를 설정한다.

- 프론트엔드
  - 개발 서버(`vite dev`)에서는 테스트 페르소나 모드가 자동 활성화된다.
  - 로그인 후 `/persona-select`에서 `HQ_ADMIN` / `SITE_MANAGER` / `WORKER`를 고른다.
- 백엔드(선택)
  - `BESMA_TEST_PERSONA_MODE=true` 이면 worker 서명 GPS 반경 검증이 테스트 반경으로 동작한다.
  - `BESMA_TEST_GPS_RADIUS_M=5` (기본값 5)
  - 테스트 모드가 아니면 기존 `site.allowed_radius_m` 정책을 그대로 사용한다.

## 7. 모바일/PC UI 동선

실사용 점검용 UI 경로:

- 근로자 모바일(로그인 없이 access_token 기반)
  - `http://118.36.137.127:5174/worker/mobile`
- 현장관리자 모바일(로그인 필요)
  - `http://118.36.137.127:5174/site/mobile`
- 본사관리자 PC 모니터(로그인 필요)
  - `http://118.36.137.127:5174/hq-safe/tbm-monitor`
- 현장 문서 운영 대시보드(로그인 필요)
  - `http://127.0.0.1:5174/site/documents`
- 본사 문서 운영 대시보드(로그인 필요)
  - `http://127.0.0.1:5174/hq-safe/documents`
- 본사 현장관리 조회(로그인 필요)
  - `http://127.0.0.1:5174/hq-safe/sites`
- 본사 사용자관리 조회(로그인 필요)
  - `http://127.0.0.1:5174/hq-safe/users`

프론트 API 주소 정책:

- `VITE_API_BASE_URL` 환경변수가 있으면 해당 값 사용
- 없으면 현재 접속한 호스트를 기준으로 `:8001`을 자동 사용
  - 예: `http://118.36.137.127:5174` 접속 시 API는 `http://118.36.137.127:8001`

## 8. 문서 운영 API 요약

문서 운영형 화면에서 사용하는 핵심 API:

- requirement 상태 조회
  - `GET /documents/requirements/status?site_id={id}&period=all|day|week|month|quarter|half_year|year|event&date=YYYY-MM-DD`
- HQ 대시보드 집계
  - `GET /documents/hq-dashboard?period=...&date=YYYY-MM-DD&site_id={optional}`
- 문서 업로드(기존 진입점 유지)
  - `POST /document-submissions/upload`
- 리뷰/승인/반려(기존 진입점 유지)
  - `POST /documents/{document_id}/review`
- requirement 기준 업로드 이력 조회
  - `GET /documents/history?site_id={id}&requirement_id={id}`
- 메뉴 배지 집계
  - `GET /documents/badges/site?date=YYYY-MM-DD`
  - `GET /documents/badges/hq?date=YYYY-MM-DD`

## 9. 반려 샘플 데이터

시연용 반려-재업로드 흐름을 위해 seed에 반려 샘플 1건을 유지한다.

- seed 실행: `cd backend && .venv\\Scripts\\python.exe -m app.seed.seed_data`
- 샘플 특징:
  - status: `REJECTED`
  - rejection reason: `위험요인/대책 부적절`
  - description marker: `[SAMPLE_REJECTED_FLOW]`