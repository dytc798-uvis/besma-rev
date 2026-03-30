# BESMA_SESSION_STATE

> 경고: 이 파일은 작업 시작 시 반드시 읽고, 작업 후 반드시 업데이트해야 한다.
> 이 문서는 정적 설명 문서가 아니라 세션 상태를 이어가기 위한 동적 상태 파일이다.
> 필수 참조 문서: `docs/ai_collaboration_policy.md`, `docs/BESMA_SESSION_STATE.md`, `docs/SESSION_START_REQUIRED.md`

## 1. 현재 기준 프로젝트

- 프로젝트명: BESMA 로컬 MVP
- 워크스페이스 절대경로: `D:\besma-rev`
- 프로젝트 유형: `FastAPI + Vue 3 + TypeScript + Vite + SQLite`
- 실행 포트
  - backend: `127.0.0.1:8001`
  - frontend: `127.0.0.1:5174`
- 기준 프로젝트 판정 메모
  - 현재 세션의 기준 프로젝트는 `D:\besma-rev` 로컬 MVP이다.
  - `C:\BESMA`는 별도 기존 프로젝트로 간주하며 동일 프로젝트로 취급하지 않는다.
  - 작업 시작 전 반드시 실제 워크스페이스 절대경로를 다시 확인한다.

## 2. 현재 개발 단계

- 현재 단계: 로컬 MVP 통합 안정화 단계
- 핵심 목표
  - 로컬 환경에서 백엔드와 프론트엔드가 정상 연동되어 로그인부터 주요 화면 진입까지 안정적으로 동작하도록 유지
  - 경로 혼동, 포트 불일치, CORS, 인증, DB 초기화 문제를 우선 제거
  - 후속 작업자가 현재 상태를 즉시 이해하고 이어서 작업할 수 있도록 세션 정보를 누적 기록
- 진행 중 작업
  - [x] 백엔드 CORS 및 프론트 API 연결 기본값 확인
  - [x] `/health` 엔드포인트 존재 여부 확인
  - [x] AI 협업 통합운영규정 문서화
  - [ ] 실제 로그인 요청 브라우저 기준 재현 검증
  - [ ] 주요 기능별 상태 점검표 상세화

## 3. 세션 시작 체크리스트

작업 시작 시 아래 항목을 확인한 뒤 필요한 항목을 갱신한다.

- [ ] `docs/ai_collaboration_policy.md`를 읽고 Instruction Validation Gate / Invariant Check 규정을 확인했다.
- [ ] `docs/BESMA_SESSION_STATE.md` 최신 상태를 읽고 현재 세션 기준을 확인했다.
- [ ] `docs/SESSION_START_REQUIRED.md`를 읽고 필수 참조 문서를 다시 확인했다.
- [ ] 현재 워크스페이스가 `D:\besma-rev`인지 확인했다.
- [ ] `C:\BESMA`와 혼동하지 않았는지 확인했다.
- [ ] 현재 프로젝트가 `FastAPI + Vue3` 구조인지 확인했다.
- [ ] backend 실행 포트가 `8001`인지 확인했다.
- [ ] frontend 실행 포트가 `5174`인지 확인했다.
- [ ] 오늘 작업 목적을 아래 7번 항목에 반영했다.
- [ ] 수정 허용 범위와 수정 금지 범위를 확인했다.
- [ ] 관련 기준 문서 존재 여부를 확인했다.
- [ ] Instruction Validation Gate를 수행했다. (모호/위험/정책충돌 지시는 확인 후 진행)

## 4. 최근 작업 이력

아래 형식으로 최신 작업을 위에 추가한다.

### 2026-03-20

- 작업자: Codex
- 작업 목적: 문서 운영 시연 구조 보강(HQ 현장 중심 모니터 + Site 할일 중심 + 반려 재업로드 이력 + 관리 조회/배지)
- 수행 내용(코드 기준)
  - backend
    - `document_upload_histories` 테이블 추가(Alembic `20260320_0018`)
    - requirement 상태 계산 정합성 보강
      - `DocumentInstance.selected_requirement_id` 우선 + code/master code fallback 조회
      - period 필터 확장: `all/day/week/month/quarter/half_year/year/event`
    - API 추가/확장
      - `GET /documents/history`
      - `GET /documents/badges/site`
      - `GET /documents/badges/hq`
      - `GET /documents/hq-dashboard`에 `site_id` 필터 지원
    - 업로드 처리 보강
      - 재업로드 시 `version_no` 증가
      - 업로드 전/후 snapshot을 `document_upload_histories`에 저장
      - 업로드 후 문서 상태를 `SUBMITTED`로 복구
    - 반려 샘플 데이터 시드 추가
      - reason: `위험요인/대책 부적절`
  - frontend
    - HQ 문서 화면을 좌측 현장 목록 + 우측 현장별 상세 구조로 전환
    - Site 문서 화면을 미완료 우선/재업로드/이력보기 중심으로 전환
    - HQ 현장관리(`/hq-safe/sites`), 사용자관리(`/hq-safe/users`) 조회 페이지 추가
    - HQ/Site 좌측 메뉴에 실시간 미완료 배지 연동
- 테스트/검증
  - `python -m pytest tests/test_document_dashboard_flow.py tests/test_document_flow_basic.py tests/test_daily_work_plan_mvp_flow.py` -> `6 passed`
  - `python -m alembic upgrade head` -> 성공(`20260320_0018`)
  - `python -m app.seed.seed_data` -> 성공(반려 샘플 반영)
  - `npm run build` -> 성공
  - `ReadLints`(수정 파일) -> 에러 없음
- 현재 판정
  - HQ/Site 문서 운영 화면이 시연 중심 구조로 전환됐고, 반려->재업로드->이력 가시화 및 메뉴 배지/관리 조회 화면이 동작함

### 2026-03-20

- 작업자: Codex
- 작업 목적: 현장/HQ 문서 운영 대시보드(요구문서 상태 + 승인/반려 모니터링) 구현
- 수행 내용(코드 기준)
  - backend
    - `document_requirements`에 운영 대시보드용 필드 추가(code/title/frequency/is_required/display_order/due_rule_text/note)
    - API 추가
      - `GET /documents/requirements/status?site_id=&period=day|week|month&date=YYYY-MM-DD`
      - `GET /documents/hq-dashboard?period=day|week|month&date=YYYY-MM-DD`
    - 업로드 보강
      - `POST /document-submissions/upload`에 `requirement_id` 입력 시 requirement 주기에 맞는 period 계산/연결
      - 기존 `instance_id` 및 기존 업로드 진입점 유지
    - seed 보강
      - 일간/주간/월간/1회성/이벤트/상시(ROLLING) 대표 요구문서 19종을 site별 requirement로 upsert
    - alembic 추가
      - `20260320_0017`(파일명: `20260320_0015_document_requirement_dashboard_fields.py`)
  - frontend
    - `/site/documents`를 현장용 대시보드로 교체
      - 오늘/이번주/이번달 탭, 요약카드, 상태표, requirement 기반 업로드
    - `/hq-safe/documents`를 HQ 모니터 대시보드로 교체
      - 전체/승인대기/반려/미제출 요약, 현장별 제출률, 문서 상태표, 검토시작/승인/반려 액션
    - 라우터 연결
      - `SiteDocumentsDashboardPage.vue`, `HQDocumentsDashboardPage.vue` 연결
- 테스트/검증
  - `python -m pytest tests/test_document_dashboard_flow.py tests/test_document_flow_basic.py tests/test_daily_work_plan_mvp_flow.py` -> `6 passed`
  - `npm run build` -> 성공
  - `alembic upgrade head` + `python -m app.seed.seed_data` -> 성공
  - `ReadLints`(수정 파일) -> 에러 없음
- 현재 판정
  - 기존 upload/review 단일 진입점은 유지한 채, period별 제출대상 가시화 및 HQ 승인/반려 운영 대시보드 골격 구현 완료

### 2026-03-19

- 작업자: Codex
- 작업 목적: `/site/mobile`에서 현재 시나리오와 최근 배포 이력이 섞이는 문제 및 배포 생성 비활성 문제 보정
- 수행 내용(코드 기준)
  - `frontend/src/pages/site/SiteMobileOpsPage.vue`
    - `hasAdoptedItems` 계산 기준을 `risk_refs.status`에서 `risk_refs.link_type/is_selected` 기반으로 수정
    - 페이지 진입 시 최근 배포 자동 선택 로직 제거 (현재 시나리오 자동 오염 방지)
    - `새 작업 시작` 버튼 추가 및 `currentPlan/currentDistribution` 상태 초기화 구현
    - 시나리오 초기화 시 하위 컴포넌트 상태까지 초기화되도록 `scenarioEpoch` key 리마운트 적용
  - `frontend/src/components/site/SiteDistributionCreateCard.vue`
    - plan 변경 시 이전 시나리오의 worker 선택/메시지 상태를 초기화하고 필요 시 worker 목록 재로딩
  - `frontend/src/components/site/SiteTbmOpsPanel.vue`
    - 안내 문구를 “현재 시나리오 배포 없음” 중심으로 변경
    - 최근 배포 섹션 제목을 “수동 불러오기”로 명시해 운영 이력과 현재 시나리오를 분리
- 테스트/검증
  - `npm run build` -> 성공
  - `ReadLints`(수정 파일) -> 에러 없음
  - 브라우저 자동화 검증은 실행 도구 미가용으로 블록됨(코드 경로/상태 전이 기준 점검 완료)
- 현재 판정
  - 채택 반영 계산 오류와 자동 최근 배포 선택 문제를 제거해 테스트/운영 혼선을 줄였음
  - 실제 브라우저 상호작용 검증은 사용자의 로컬 브라우저에서 최종 확인 필요

### 2026-03-19

- 작업자: Codex
- 작업 목적: 위험요인 추천 품질 보정으로 사무성 작업 과추천을 억제하고 배관 계열 작업 추천 안정화
- 수행 내용(코드 기준)
  - `backend/app/modules/risk_library/service.py`
    - 추천 텍스트 정규화/토큰 추출/위치성 노이즈 제거 로직 추가
    - `도면/서류/검토/회의/교육` 등 사무성 키워드 감지 시 현장 물리위험 점수 강한 감점 적용
    - `배관`, `벽체 배관`, `천장슬라브 배관`, `슬라브 배관` 등 명시 작업 키워드 hit 시 관련 revision을 강하게 우선 추천
    - exact keyword 1차 매칭 후 revision 텍스트 기반 2차 fallback을 추가해 keyword가 부족해도 배관 계열 후보가 뜨도록 보강
  - `backend/app/seed/seed_data.py`
    - 기본 배관 위험 revision 3종(천장슬라브 배관, 벽체 배관, 전선관 배관) 시드 추가
    - keyword 생성 시 `작업` 등 일반어 stopword 제거 및 `천장슬라브 배관` 같은 2단어 phrase keyword 생성 보강
  - `backend/tests/test_risk_library_service.py`
    - 사무성 작업 과추천 억제 테스트 추가
    - 배관 작업 keyword 없는 상태 fallback 추천 테스트 추가
- 테스트/검증
  - `python -m pytest backend/tests/test_risk_library_service.py` -> `3 passed`
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` -> `3 passed`
  - 실DB 기준 대표 입력 검증
    - `도면 및 서류 검토 작업` -> `0건`
    - `헬스케어센터 지하3층 천장슬라브 배관` -> 배관 관련 위험 `3건`
    - `7002동 지상1층 벽체 배관` -> 배관 관련 위험 `3건`
    - `7010동 및 주변 지하5층 천장슬라브 배관` -> 배관 관련 위험 `3건`
- 현재 판정
  - 일반어 `작업` 때문에 발생하던 과추천이 제거되었고, 배관 계열 작업은 explicit/fallback 규칙으로 상위 추천이 안정화됨
  - 기존 plan/recommend/adopt/distribution/sign 흐름은 유지

### 2026-03-19

- 작업자: Codex
- 작업 목적: 테스트 단계 검증용으로 근로자 상세 화면에 작업내용/위험요인/대책을 표시하고 HQ PC 화면에서 서명 이미지를 직접 확인 가능하게 보강
- 수행 내용(코드 기준)
  - `frontend/src/pages/worker/WorkerMobileDetailPage.vue`
    - worker 상세 화면에 `plan.items` 렌더링 추가
    - 항목별로 `작업명`, `작업내용`, `팀`, `위험요인`, `대책`, `위험도` 표시
    - 근로자가 내용을 확인한 뒤 바로 `sign-start` / `sign-end` 수행 가능하도록 구성
  - `frontend/src/pages/hq/HQTbmMonitorPage.vue`
    - TBM 요약 표에 `시작 이미지`, `종료 이미지` 컬럼 추가
    - `tbm-summary.table_rows`를 이용해 `작업내용/위험요인/대책` 테이블도 함께 표시
    - 결과적으로 HQ/관리자 PC에서 "무엇을 기준으로 서명했는지 + 누가 어떻게 서명했는지"를 한 화면에서 확인 가능
- 테스트/검증
  - `npm run build` -> 성공
  - `ReadLints`(수정 파일) -> 에러 없음
- 현재 판정
  - 테스트 단계에서 worker가 내용을 보고 서명하고 HQ가 서명 결과를 시각적으로 확인하는 최소 검증 UI 확보
  - 실제 운영 검증은 site GPS 좌표/반경과 TBM 시작/ping 데이터가 갖춰져야 완료 가능

### 2026-03-19

- 작업자: Codex
- 작업 목적: 비로그인 상태의 `/worker/mobile` 진입 시 공통 로그인 화면으로 즉시 리다이렉트되도록 보정
- 수행 내용(코드 기준)
  - `frontend/src/router/index.ts`
    - `worker-mobile-list`, `worker-mobile-detail` 진입 시
      - `auth.isAuthenticated == false`
      - `query.access_token 없음`
      조건이면 `/login?redirect=...` 으로 즉시 이동하도록 라우팅 가드 추가
    - 결과적으로 비로그인 사용자는 worker 안내 문구 화면이 아니라 로그인 화면을 먼저 보게 됨
- 테스트/검증
  - `npm run build` -> 성공
  - `ReadLints`(수정 파일) -> 에러 없음
- 현재 판정
  - 로그인된 WORKER는 기존처럼 자동 조회
  - 비로그인 + access_token 있음은 보조 링크 진입 유지
  - 비로그인 + access_token 없음만 공통 로그인 화면으로 이동

### 2026-03-19

- 작업자: Codex
- 작업 목적: 실제 실행 실패(CORS/site context/worker 로그인 자동조회 불일치) 복구
- 수행 내용(코드 기준)
  - 프론트 초기 인증 복구
    - `frontend/src/main.ts`
    - localStorage에 token만 있고 `auth.user`가 비어 있는 경우 앱 부팅 시 `loadMe()` 실행
    - 실패 시 `logout()` 처리
  - backend 실행 시 DB 정합성 복구
    - `run_backend.bat`
    - 서버 시작 전 `alembic upgrade head` + `python -m app.seed.seed_data` 자동 실행
  - Alembic 이력/실DB 불일치 보정
    - `backend/alembic/versions/20260318_0009_daily_work_plan_document_links.py`
    - `backend/alembic/versions/20260318_0010_daily_work_plan_distribution_and_signature.py`
    - `backend/alembic/versions/20260318_0011_tbm_start_end_signature_flow.py`
    - `backend/alembic/versions/20260319_0012_distribution_tbm_start_gate.py`
    - `backend/alembic/versions/20260319_0013_user_person_link_for_worker_login.py`
    - 이미 테이블/컬럼/인덱스가 존재하는 실DB에서도 `upgrade head`가 실패하지 않도록 idempotent 보강
- 테스트/검증
  - 실제 `database/besma.db`에 `alembic upgrade head` 성공
  - 실제 `database/besma.db`에 `seed_data` 반영 후 `worker01/worker02`, `site01/site02` 계정 확인
  - 실제 backend 실행 후 `/sites`:
    - `GET /sites` + Origin `http://127.0.0.1:5174` -> 200, ACAO 정상
    - `OPTIONS /sites` + Origin `127/localhost/192.168.219.51:5174` -> 모두 200
  - 실제 worker 로그인 API:
    - `worker01` 로그인 후 `/worker/my-daily-work-plans` -> 200
  - 실제 access_token 보조 흐름:
    - `distribution_id=1` 토큰으로 `/worker/my-daily-work-plans?access_token=...` -> 200
  - `npm run build` -> 성공
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` -> `3 passed`
- 현재 판정
  - 이전 불일치의 핵심 원인은 "코드 반영"이 아니라 "실DB 미마이그레이션 + 프론트 부팅 시 auth.user 미복구"였다
  - 현재 로컬 기준 `/sites` CORS와 worker 로그인 자동조회 API는 실제 서버에서 정상 확인

### 2026-03-19

- 작업자: Codex
- 작업 목적: WORKER 진입 기본 흐름을 access_token 링크에서 로그인 기반 자동 조회로 전환
- 수행 내용(코드 기준)
  - 백엔드 worker API를 `로그인/토큰` 겸용으로 확장
    - `backend/app/modules/risk_library/routes.py`
      - `/worker/my-daily-work-plans*` 및 `sign-start/sign-end`에서 `access_token` 없이도 Bearer 로그인 사용자(`users.person_id`) 기반 처리 지원
    - `backend/app/modules/risk_library/service.py`
      - worker 식별 로직을 `access_token` 또는 `person_id` 기반으로 공통화
  - 사용자-근로자 연결 필드 추가
    - `backend/app/modules/users/models.py`: `person_id` FK 추가
    - `backend/alembic/versions/20260319_0013_user_person_link_for_worker_login.py` 마이그레이션 추가
    - `backend/app/schemas/auth.py`: `/auth/me` 응답에 `person_id` 포함
  - 근로자 요청 스키마 보강
    - `backend/app/schemas/daily_work_plans.py`
    - `WorkerSignDailyWorkPlanRequest` / `WorkerSignEndDailyWorkPlanRequest`의 `access_token`을 optional로 변경
  - 프론트 worker UI를 로그인 기본 흐름으로 전환
    - `frontend/src/pages/worker/WorkerMobileListPage.vue`
      - 토큰 없으면 즉시 차단하던 구조 제거
      - 로그인 사용자 자동 조회 + 토큰 링크 보조 지원
    - `frontend/src/pages/worker/WorkerMobileDetailPage.vue`
      - 상세/서명 API 호출 시 토큰이 있을 때만 포함
      - 오프라인 큐도 `access_token nullable` 호환
    - `frontend/src/services/offlineSignQueue.ts`
      - queue item의 `access_token` 타입을 `string | null`로 확장
  - 로그인 라우팅 보정
    - `frontend/src/pages/LoginPage.vue`, `frontend/src/router/index.ts`, `frontend/src/stores/auth.ts`
    - `role == WORKER` 사용자는 로그인 후 `worker-mobile-list`로 진입
  - 시드 보강
    - `backend/app/seed/seed_data.py`
    - 샘플 worker 계정(`worker01`, `worker02`)과 person/employment 연계 보강
- 테스트/검증
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` -> `3 passed`
  - `npm run build` -> 성공
  - `ReadLints`(수정 프론트 파일) -> 에러 없음
- 현재 판정
  - 운영 기본 흐름을 로그인 기반으로 전환했으며 기존 token 링크 흐름은 보조/예외 경로로 유지
  - GPS / 관리자 presence / TBM start gate / sign-start / sign-end 규칙은 유지

### 2026-03-19

- 작업자: Codex
- 작업 목적: 세션 이동용 인계 프롬프트 최신화 + SITE context/근로자 링크 운영 이슈 상태 반영
- 수행 내용(코드/운영 기준)
  - 상태 점검
    - `site context가 없습니다` 이슈 원인 확인:
      - `hqsafe1` 계정은 실제 `site_id = null`
      - 테스트 페르소나 `SITE_MANAGER` 오버레이 시 fallback context가 필요
    - DB 점검:
      - `sites` 테이블 데이터 존재(빈 테이블 아님)
      - `users`에 `site01/site02` 등 실제 SITE 계정 존재
  - UX 보정
    - `frontend/src/pages/site/SiteMobileOpsPage.vue`
      - `/sites` 조회 실패를 사용자 메시지로 노출
      - 현장 목록 로딩 상태 표시 및 빈 목록 안내 문구 추가
  - 운영 동선 확인
    - 관리자 화면에서 worker별 `access_token`/접속 링크 복사 가능
    - 근로자 화면은 token 링크 진입 전제 구조 유지
- 테스트/검증
  - `npm run build` -> 성공
  - `ReadLints`(수정 파일) -> 에러 없음
  - SQLite 조회로 `sites/users` 데이터 존재 확인
- 현재 판정
  - 기술적으로 "관리자가 링크 배포" 구조가 맞으며, 소규모는 가능
  - 대규모(예: 200명)에서는 수동 복사/전송 부담이 커서 `일괄 링크 복사/CSV 내보내기` 개선이 다음 우선 과제

### 2026-03-19

- 작업자: Codex
- 작업 목적: SITE context 없는 테스트 페르소나 진입 보정 + 근로자 token 링크 UX/복사 동선 보완
- 수행 내용(코드 기준)
  - 테스트 모드 SITE_MANAGER fallback site context 추가
    - `frontend/src/stores/auth.ts`
    - `testSiteContextId`, `effectiveSiteId` 추가
    - 로그아웃 시 테스트 site context 초기화
  - SITE 관리자 모바일 운영 화면 보정
    - `frontend/src/pages/site/SiteMobileOpsPage.vue`
    - 테스트 모드에서 `auth.user.site_id`가 없는 경우 `/sites` 목록 기반 context 선택 UI 추가
    - 관리자 ping 시 `site_id` 해석 우선순위 개선:
      - `auth.user.site_id` -> `distribution.site_id` -> `auth.effectiveSiteId`
    - distribution worker 카드에 `access_token` 표시 및
      - `토큰 복사`
      - `근로자 링크 복사` (`/worker/mobile?access_token=...`)
      버튼 추가
  - WORKER 직접 진입 안내 문구 개선
    - `frontend/src/pages/worker/WorkerMobileListPage.vue`
    - token 없는 경우 안내를 전용 링크 형식 예시까지 포함하도록 변경
- 테스트/검증
  - `npm run build` -> 성공
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` -> `3 passed`
  - `ReadLints`(수정 파일) -> 에러 없음
- 현재 판정
  - SITE context 없는 persona overlay 계정도 테스트 모드에서 context 선택 후 site 운영 화면 테스트 가능
  - WORKER는 token 없는 직접 진입 시 명확한 안내를 받고, 관리자 화면에서 링크를 즉시 복사 가능

### 2026-03-19

- 작업자: Codex
- 작업 목적: TEST MODE 전용 offline sign queue 추가 및 테스트 허브 운영 동선 분리 유지
- 수행 내용(코드 기준)
  - 테스트 모드 전용 queue 유틸 추가
    - `frontend/src/services/offlineSignQueue.ts`
    - 저장 키: `besma_pending_sign_queue`
    - 저장 필드: `distribution_id`, `access_token`, `sign_type`, `lat`, `lng`, `timestamp`, `signature_data`, `signature_mime`, `end_status`
  - 근로자 모바일 상세 화면에 재전송 기능 추가
    - `frontend/src/pages/worker/WorkerMobileDetailPage.vue`
    - 네트워크 오류(응답 없음) 시 임시 저장
    - `미전송 서명 재전송` 버튼으로 queue 순차 재전송
    - 성공 시 queue 제거/성공 메시지, 실패 시 서버 detail 우선 표시
  - 테스트 허브 분리 보강(운영 경로 미노출)
    - `frontend/src/router/index.ts`
    - `frontend/src/pages/PersonaSelectPage.vue`
    - `frontend/src/layouts/HQSafeLayout.vue`
    - `frontend/src/layouts/SiteLayout.vue`
    - `frontend/src/pages/worker/WorkerMobileListPage.vue`
    - `frontend/src/pages/site/SiteMobileOpsPage.vue`
    - `frontend/src/pages/LoginPage.vue`
- 테스트/검증
  - `npm run build` → 성공
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` → `3 passed`
  - `ReadLints`(수정 파일) → 에러 없음
- 현재 판정
  - 테스트 모드에서만 offline sign queue 노출/동작
  - 운영 모드 backend 로직 영향 없음
  - 테스트 허브는 `/dev/*` 전용 유지

### 2026-03-19

- 작업자: Codex
- 작업 목적: 사용자 동선에서 테스트 허브 분리(`/dev/*` 전용) 및 운영 UI 기본 진입 경로 보정
- 수행 내용(코드 기준)
  - 라우팅 분리
    - 테스트 허브 라우트를 운영 경로에서 제거하고 `/dev/*` 전용으로 이동
      - `/dev/hq-test`, `/dev/site-test`, `/dev/worker-test`
    - 테스트 페르소나 기본 진입을 운영 UI로 변경
      - `WORKER -> /worker/mobile`
      - `SITE_MANAGER -> /site/mobile`
      - `HQ_ADMIN -> /hq-safe/tbm-monitor`
  - 레이아웃 메뉴 정리
    - 운영 사이드바에서 테스트 허브 메뉴 제거(HQ/SITE)
  - WORKER 운영 UI 보정
    - `WorkerMobileListPage.vue`, `WorkerMobileDetailPage.vue`에서 수동 입력 필드 제거
    - `access_token`은 링크 query 기반으로만 처리(토큰 없으면 안내 메시지)
  - SITE_MANAGER 운영 UI 보정
    - `SiteMobileOpsPage.vue`에서 수동 입력(`plan_id/person_ids/distribution_id`) 제거
    - 최근 배포 선택 + URL query(`distribution_id`) 기반 상세 운영으로 전환
  - 로그인/페르소나 진입 보정
    - `LoginPage.vue`, `PersonaSelectPage.vue`, `router.beforeEach` 리다이렉트 목적지 정합화
- 테스트/검증
  - `npm run build` → 성공
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` → `3 passed`
  - `ReadLints`(수정 파일) → 에러 없음
- 현재 판정
  - 테스트 허브는 유지되되 `/dev/*` 경로에서만 접근
  - 로그인 후 사용자 기본 동선은 운영 UI로 연결
  - backend API/workflow/signature 로직 영향 없음

### 2026-03-19

- 작업자: Codex
- 작업 목적: 로그인 API 200 성공인데 프론트 실패 표시되는 현상 수정
- 수행 내용(코드 기준)
  - 원인 분석
    - `POST /auth/login`은 200 성공이나, 프론트 접속 origin이 `http://192.168.219.51:5174`일 때 CORS 허용 목록에 없어서 브라우저가 응답/후속 호출을 차단
    - 기존 로그인 페이지 catch 문이 모든 예외를 인증 실패로 처리해 오진 메시지 출력
  - 수정 사항
    - `backend/app/config/settings.py`
      - CORS origin에 `http://192.168.219.51:5174` 추가
    - `frontend/src/pages/LoginPage.vue`
      - 로그인 오류 메시지 분기 처리:
        - 실제 401(`/auth/login`)만 ID/비밀번호 오류 메시지 표시
        - `/auth/me` 또는 네트워크/CORS 계열 오류는 별도 안내 문구 표시
- 테스트/검증
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` → `3 passed`
  - `npm run build` → 성공
  - `ReadLints`(수정 파일) → 에러 없음
- 현재 판정
  - backend 인증 로직 변경 없이 최소 수정으로 증상 원인 지점(CORS + 프론트 에러 오분류) 보정 완료

### 2026-03-19

- 작업자: Codex
- 작업 목적: PC + 모바일 + 외부망 실환경 실행 검증 시나리오 설계/디버깅 기준 정리
- 수행 내용(문서 기준)
  - 실환경 검증 단계를 `PC 기동 -> 외부망 -> API/CORS -> 모바일 근로자 -> 모바일 관리자 -> HQ 모니터` 순으로 구조화
  - 단계별로 `목적/실행방법/성공기준/실패기준/원인후보/로그위치`를 명시해 즉시 장애지점 식별 가능하도록 정리
  - 모바일 특화 실패 케이스 추가:
    - GPS 권한 거부
    - HTTP 환경 위치 제한 가능성
    - 네트워크 단절
    - Wi-Fi <-> LTE 전환
  - 위험 실패 포인트 TOP5 및 장애 대응 디버깅 순서 정의
  - 현장 즉시 사용 가능한 최소 실행 체크리스트 작성
- 테스트/검증
  - 본 항목은 코드 변경이 아닌 운영 검증 설계 문서화 단계
- 현재 판정
  - 기능 테스트를 넘어 장애 추적 중심의 실행 검증 체계를 확보
  - 현장/본사에서 동일 기준으로 문제 재현 및 원인 추적 가능

### 2026-03-19

- 작업자: Codex
- 작업 목적: Mobile Worker / Mobile Manager / Desktop HQ 실사용 UI 동선 구성
- 수행 내용(코드 기준)
  - 근로자 모바일 동선 추가(무로그인 token 기반)
    - `frontend/src/pages/worker/WorkerMobileListPage.vue`
    - `frontend/src/pages/worker/WorkerMobileDetailPage.vue`
    - `frontend/src/components/SignaturePad.vue`
    - 기능: access_token 조회, 상세 열람, sign-start/sign-end, 위치 권한 요청, 성공/실패 메시지 표시
  - 현장관리자 모바일 운영 화면 추가
    - `frontend/src/pages/site/SiteMobileOpsPage.vue`
    - 기능: distribution 생성/조회, TBM 시작, 관리자 presence ping, 서명 진행률(전체/시작/종료/issue) 표시
  - 본사관리자 PC 모니터 화면 추가
    - `frontend/src/pages/hq/HQTbmMonitorPage.vue`
    - 기능: 문서 목록/선택, tbm-summary 조회, TBM view·문서상세 이동, 참여자 서명 현황/issue 집계 표시
  - 라우팅/메뉴 연결
    - `frontend/src/router/index.ts`
      - `/worker/mobile`, `/worker/mobile/:distributionId`, `/site/mobile`, `/hq-safe/tbm-monitor`
    - `HQSafeLayout.vue`, `SiteLayout.vue`에 메뉴 연결
  - 네트워크 접속/환경 보정
    - `frontend/src/services/api.ts`
      - `VITE_API_BASE_URL` 우선, 미설정 시 현재 접속 host 기준 `:8001` 자동 사용
    - `frontend/vite.config.ts`
      - `host: true`, `port: 5174`, `strictPort: true`
    - `backend/app/main.py`
      - CORS를 `settings.cors_origins` 기반으로 통합
    - `backend/app/config/settings.py`
      - 기본 CORS origin에 `http://118.36.137.127:5174` 포함
    - BAT 수정
      - `run_backend.bat`: host `0.0.0.0:8001`
      - `run_frontend.bat`: host `0.0.0.0:5174`
      - `run_local_mvp.bat`: 외부 접속 URL 출력 추가
  - 문서 반영
    - `docs/README.md`에 모바일/PC UI 경로 및 API baseURL 정책 추가
- 테스트/검증
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` → `3 passed`
  - `npm run build` → 성공
  - `ReadLints`(변경 파일) → 에러 없음
- 현재 판정
  - 휴대폰에서 근로자/현장관리자 동선 진입 가능한 UI 확보
  - PC에서 본사 TBM 모니터링 동선 확보
  - 기존 backend workflow/distribution/signature 정책 영향 없이 UI 연결 완료

### 2026-03-19

- 작업자: Codex
- 작업 목적: TBM 시작(start-tbm) 게이트 기반 근로자 sign-start 개방 정책 반영
- 수행 내용(코드 기준)
  - DB/모델 확장
    - `daily_work_plan_distributions`에 `tbm_started_at`, `tbm_started_by_user_id`, `tbm_closed_at` 추가
    - Alembic revision 추가: `20260319_0012_distribution_tbm_start_gate.py`
  - 서비스/라우트 확장
    - 관리자 API 추가: `POST /daily-work-plans/distributions/{distribution_id}/start-tbm` (idempotent)
    - distribution 조회 응답에 `tbm_started_at`, `tbm_started_by_user_id`, `is_tbm_active` 포함
    - worker sign-start/sign-end 검증에 `tbm_started_at` 존재 조건 추가
  - 메시지 정책 반영
    - TBM 시작 전: `아직 TBM이 시작되지 않았습니다. 관리자 안내 후 서명하세요.`
    - GPS 반경 밖: `관리자가 있는 TBM장소로 이동하여 서명하세요.`
    - sign-start 성공: `안전하지 않으면 작업하지 않습니다. 위험한 상황은 바로 신고바랍니다.`
  - 프론트 테스트 허브 반영
    - `SITE_MANAGER` 테스트 허브에 `TBM 시작` 버튼/상태(`시작 여부`, `시각`) 추가
  - 테스트 보강
    - TBM 시작 전 sign-start 실패 검증
    - start-tbm 2회 호출 idempotent 검증
    - start-tbm 후 sign-start 성공 및 기존 sign-end/tbm-summary 회귀 검증
- 테스트/검증
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` → `3 passed`
  - `python -m alembic upgrade head` (임시 sqlite) → `20260319_0012`까지 성공
  - `npm run build` → 성공
- 현재 판정
  - distribution만으로는 sign-start 불가
  - 관리자 start-tbm 호출 이후에만 sign-start 가능
  - 기존 GPS/presence/sign-end/TBM view 흐름 회귀 없음

### 2026-03-18

- 작업자: Codex
- 작업 목적: TEST PERSONA MODE + 테스트 전용 GPS 5m 정책 추가
- 수행 내용(코드 기준)
  - 프론트 테스트 페르소나 오버레이 추가(운영 권한 불변)
    - `frontend/src/stores/auth.ts`
      - `selectedPersona`, `effectivePersona`, `effectiveUiType`, `isTestPersonaMode(import.meta.env.DEV)` 추가
      - `setPersona`, `clearPersona`로 세션 기반 오버레이 제어
    - `frontend/src/router/index.ts`
      - `/persona-select` 라우트와 `WORKER` 전용 `/worker-test` 라우트 추가
      - 테스트 모드에서 로그인 후 페르소나 선택 강제 및 persona/uiType 기반 가드 적용
    - `frontend/src/pages/PersonaSelectPage.vue` 생성
      - HQ_ADMIN / SITE_MANAGER / WORKER 선택 UI 추가
    - 레이아웃/목록 페이지 보정
      - `HQSafeLayout.vue`, `SiteLayout.vue`, `HQOtherLayout.vue` 헤더에 Persona 표시 및 전환 버튼 추가
      - `DocumentListPage.vue`가 실제 `user.ui_type` 대신 `effectiveUiType` 기반으로 동작하도록 수정
    - 테스트 허브 페이지 추가
      - `TestHQAdminPage.vue`: TBM summary 조회/이동
      - `TestSiteManagerPage.vue`: DailyWorkPlan 작성~배포~presence ping 테스트 동선
      - `TestWorkerPage.vue`: worker list/detail/sign-start/sign-end 테스트 동선
  - 백엔드 테스트 모드 GPS 반경 분리
    - `backend/app/config/settings.py`
      - `BESMA_TEST_PERSONA_MODE`, `BESMA_TEST_GPS_RADIUS_M` 설정값 추가
    - `backend/app/modules/risk_library/service.py`
      - worker 서명 검증 시 테스트 모드면 `test_gps_radius_m`(기본 5m) 사용
      - 운영 모드면 기존 `site.allowed_radius_m` 사용(기존 구조 유지)
- 테스트/검증
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` → `3 passed`
  - `npm run build` (frontend) → 성공
  - 변경 파일 대상 `ReadLints` → 에러 없음
- 현재 판정
  - 테스트 모드에서 고정 로그인 후 Persona 선택 및 UI 분기 가능
  - worker API 인증은 기존 `access_token` 구조 그대로 유지
  - GPS 반경은 테스트 모드에서만 5m로 분리 적용됨

### 2026-03-18

- 작업자: Codex
- 작업 목적: 로컬 MVP 일괄 실행 BAT(run_local_mvp) 구성 및 검증
- 수행 내용(코드 기준)
  - 루트 실행 BAT 정비
    - `run_backend.bat` 수정
      - 실행 포트 명시: `127.0.0.1:8001`
      - backend venv(`backend\.venv\Scripts\python.exe`) 존재 확인
      - 기존 잘못된 docs URL(`8000`) 자동 오픈 로직 제거
    - `run_frontend.bat` 생성
      - `frontend` 진입 후 `node_modules` 없으면 `npm install`
      - `npm run dev -- --host 127.0.0.1 --port 5174 --strictPort`로 포트 고정 실행
    - `run_local_mvp.bat` 생성
      - `BESMA Backend`, `BESMA Frontend` 제목의 별도 cmd 창에서 백/프론트 동시 실행
    - `stop_local_mvp.bat` 생성
      - 창 제목 기반 종료 + `8001/5174` LISTENING PID 종료(포트 기반 보조)
  - 문서 반영
    - `docs/README.md`에 BAT 기반 로컬 실행/종료 방법 추가
- 테스트/검증
  - `cmd /c run_local_mvp.bat` 실행 후 포트 리슨 확인
    - `127.0.0.1:8001 LISTENING`, `127.0.0.1:5174 LISTENING`
  - HTTP 응답 확인
    - `http://127.0.0.1:8001/health` → `200`
    - `http://127.0.0.1:5174` → `200`
  - `cmd /c stop_local_mvp.bat`로 종료 동작 확인
- 현재 판정
  - 로컬 MVP를 단일 BAT로 동시 실행 가능
  - 도메인/API/DB 구조 변경 없이 실행 편의만 개선

### 2026-03-18

- 작업자: Codex
- 작업 목적: TBM 문서 View/Rendering + 시작/종료 2단계 서명 흐름 확장
- 수행 내용(코드 기준)
  - 근로자 시작/종료 서명 확장
    - `daily_work_plan_distribution_workers`에 `start_signed_at`, `end_signed_at`, `end_status`, `issue_flag` 및 시작/종료 서명 데이터 필드 추가
    - 기존 `signed_at/signature_*`는 하위호환 유지(시작 서명 mirror)
    - API 추가: `POST /worker/my-daily-work-plans/{distribution_id}/sign-start`, `POST /worker/my-daily-work-plans/{distribution_id}/sign-end`
    - 정책 반영: `PENDING -> START_SIGNED -> COMPLETED`, start 없이 end 금지
  - TBM 문서 조회/렌더링 read model 추가
    - `GET /documents/{document_id}/tbm-summary` 추가
    - 기존 `GET /documents/{document_id}/content`를 재사용해 TBM 상단정보/작업-위험표/상위5위험/참석자(시작/종료 서명) 조립
  - 프론트 TBM View 페이지 구현
    - `frontend/src/pages/documents/DocumentTbmViewPage.vue`
    - 경로 추가: `/documents/:id/tbm-view` 및 각 UI layout 하위 경로
    - 모바일 대응 + print CSS(A4) 반영
  - Alembic revision 추가
    - `20260318_0011_tbm_start_end_signature_flow.py`
  - E2E 테스트 확장
    - 시작서명만 완료 아님
    - 시작 없이 종료 실패
    - 종료 NORMAL/ISSUE에 따른 `issue_flag` 검증
    - TBM summary 데이터/서명 렌더링용 응답 검증
- 테스트/검증
  - `python -m pytest backend/tests/test_daily_work_plan_mvp_flow.py` → `3 passed`
  - `python -m alembic upgrade head` (clean sqlite) → `20260318_0011`까지 성공
  - `npm run build` → 성공
- 현재 판정
  - TBM 문서 결과물 화면(`/documents/:id/tbm-view`)과 2단계 서명 백엔드 흐름 구현 완료
  - 기존 Document/workflow 핵심 구조와 기존 distribution/GPS/관리자 검증 흐름은 유지

### 2026-03-18

- 작업자: Codex
- 작업 목적: WorkPlan assemble 기반 Document Content/View Layer 구현
- 수행 내용(코드 기준)
  - 문서 내용 조회 스키마 추가
    - `backend/app/schemas/document_content.py`
  - 문서 내용 read service 추가
    - `backend/app/modules/documents/service.py`
    - `get_document_content(document_id)` 구현
    - 처리 흐름: document(instance) 조회 → linked plan/item 조회 → adopted risk(revision join) 조회 → 문서 형태 응답 조립
  - 문서 내용 조회 API 추가
    - `GET /documents/{document_id}/content`
    - 규칙 반영: `ADOPTED + is_selected=true`만 risk 포함, `risk_cause` 제외
  - 기존 문서 워크플로우 영향 없음
    - upload/review/workflow_status 전이 로직 미변경
  - E2E 테스트 확장
    - `tests/test_daily_work_plan_mvp_flow.py`에 content 조회 시나리오 추가
    - assemble 이후 content 응답 구조/필드/adopted risk 포함 검증
- 테스트/검증
  - `python -m pytest tests/test_daily_work_plan_mvp_flow.py tests/test_document_instance_status_flow.py`
  - 결과: `6 passed`
- 현재 판정
  - `/documents/{document_id}/content`를 통해 assemble된 WorkPlan을 문서형 read model로 조회 가능

### 2026-03-18

- 작업자: Codex
- 작업 목적: clean SQLite 기준 alembic migration chain 복구
- 수행 내용(코드 기준)
  - 기존 chain 실패 원인 재현
    - clean DB에서 `20260317_0002` 실행 중 `NoSuchTableError: sites` 확인
  - 근본 원인 보정
    - `20260317_0001_document_instances_basis_unique.py`에 clean DB용 core baseline table bootstrap 추가
    - 대상: `sites`, `users`, `documents`, `persons`, `employments`, `worker_import_batches`, `submission_cycles`, `document_type_masters`, `document_requirements`
    - 기존 DB에는 `check` 기반으로 무영향(skip)되도록 유지
  - migration chain self-contained 보장
    - clean DB에서 `0001 -> 0009`까지 연쇄 실행 성공 확인
- 테스트/검증
  - clean DB 마이그레이션
    - `BESMA_SQLITE_PATH=d:\\besma-rev\\backend\\storage_test\\_tmp_migration_check.db`
    - `python -m alembic upgrade head` 성공
  - 버전/핵심 테이블 확인
    - `alembic_version = 20260318_0009`
    - `sites/users/documents/document_instances/daily_work_plan_document_links` 존재 확인
  - 회귀 테스트
    - `python -m pytest tests/test_daily_work_plan_mvp_flow.py tests/test_document_generation_orchestration.py tests/test_document_instance_status_flow.py`
    - 결과: `12 passed`
- 현재 판정
  - migration chain 복구 완료
  - clean SQLite에서 migration-only 방식으로 head까지 재구성 가능

### 2026-03-18

- 작업자: Codex
- 작업 목적: DailyWorkPlan ↔ Document assemble 연결(MVP) 구현 및 idempotency 보장
- 수행 내용(코드 기준)
  - 연결 테이블 추가: `daily_work_plan_document_links`
    - 제약: `UNIQUE(instance_id, plan_id)` (보정사항 반영)
  - assemble 서비스 구현
    - `site_id + work_date + WORKPLAN_DAILY + WORKPLAN_DAY` 기준 `DocumentInstance` idempotent upsert
    - draft orchestration record 보장: `Document(instance_id)`가 없을 때만 DRAFT 생성
    - 집계 기준: 해당 일자/현장의 plan item 중 `ADOPTED + is_selected=true` 위험요인만 카운트
    - 재호출 시 instance/document/link 중복 생성 방지
    - assemble 단계에서 `workflow_status` 변경 없음
  - API 추가
    - `POST /daily-work-plans/assemble-document`
    - `GET /daily-work-plans/assembled-document`
  - 경로 충돌 방지
    - `daily-work-plans/{plan_id}`류 라우트를 `:int` path converter로 고정
  - Alembic revision 추가
    - `20260318_0009_daily_work_plan_document_links.py`
  - E2E 테스트 확장
    - `tests/test_daily_work_plan_mvp_flow.py`에 assemble/idempotency/upload-review/confirm 회귀 시나리오 추가
- 테스트/검증
  - `python -m pytest tests/test_daily_work_plan_mvp_flow.py tests/test_document_instance_status_flow.py tests/test_risk_library_service.py`
  - 결과: `7 passed`
  - 참고: clean DB에 대해 `python -m alembic upgrade head` 실행 시 기존 구간(`20260317_0002`)에서 `sites` 반영 전제 문제로 실패 확인(기존 마이그레이션 체인 이슈)
- 현재 판정
  - WorkPlan → Document assemble MVP 연결 구현 완료
  - 문서 워크플로우 invariant 유지(진입점/상태전이/FK 단일 기준)

### 2026-03-18

- 작업자: Codex
- 작업 목적: DailyWorkPlan 운영 흐름 최소 MVP API 구현 및 E2E 검증
- 수행 내용(코드 기준)
  - DailyWorkPlan 운영 API 추가
    - 생성: `POST /daily-work-plans`
    - 항목 생성: `POST /daily-work-plans/{plan_id}/items`
    - 추천 실행: `POST /daily-work-plan-items/{item_id}/recommend-risks`
    - 추천 결과 조회: `GET /daily-work-plan-items/{item_id}/risk-refs`
    - 채택: `POST /daily-work-plan-items/{item_id}/adopt-risks` (revision_id 기준)
    - 확인 이력 기록: `POST /daily-work-plans/{plan_id}/confirm`
    - 확인 이력 조회: `GET /daily-work-plans/{plan_id}/confirmations`
    - 계획 조회: `GET /daily-work-plans/{plan_id}`
  - `daily_work_plan_confirmations` 최소 테이블 추가
    - 사용자별 중복 확인 방지를 위해 `(plan_id, confirmed_by_user_id)` unique 제약 반영
  - confirm 정책 반영
    - confirm 호출 시 plan.status 자동 변경 없음 (이력만 저장)
- 테스트/검증
  - `python -m pytest tests/test_daily_work_plan_mvp_flow.py tests/test_risk_library_service.py`
  - 결과: `2 passed`
- 현재 판정
  - DailyWorkPlan 운영 흐름 최소 MVP 완료
  - 고도화 항목(권한/상태전이 정책 정교화)은 후속

### 2026-03-18

- 작업자: Cursor
- 작업 목적: 위험성평가 DB 실제 적재 및 플랫폼 표준 정규화 반영
- 수행 내용(코드 기준)
  - Risk Library / DailyWorkPlan 최소 스키마 추가
    - `risk_library_items`
    - `risk_library_item_revisions`
    - `risk_library_keywords`
    - `daily_work_plans`
    - `daily_work_plan_items`
    - `daily_work_plan_item_risk_refs`
  - `docs/safetyRisk_DB.xlsx` 기반 실제 import 스크립트 구현
    - 파일: `backend/scripts/import_safety_risk_db.py`
    - 헤더 탐지/병합셀 승계/공란 정제 포함
  - 엑셀 복제형이 아닌 플랫폼 표준 구조(`work_category/trade_type/risk_factor/risk_cause/countermeasure/F/S/R/keywords`)로 정규화 적재
  - 추천 함수(`recommend_risks_for_work_item`)가 실제 적재 데이터에서 결과를 반환하는지 검증
- 테스트/검증
  - backend pytest: `43 passed`
  - 적재 결과: item `163`, revision `163`, keyword `2128`
- 현재 판정
  - 위험성평가 DB 뼈대 + 실제 데이터 적재 완료
  - 운영 흐름(DailyWorkPlan API, 확인 이력 API)은 미완료

### 2026-03-18

- 작업자: Cursor
- 작업 목적: worker 도메인 최소 확장(MVP) 반영
- 수행 내용(코드 기준)
  - `Person.is_disabled (bool, default=false)` 컬럼 추가
  - worker import/diff/apply 구조 비파괴 유지 (샘플 기반 스모크 검증)
- 정책(문서 기준)
  - 퇴사자/재입사 원칙: Person 삭제 금지, 재입사 시 기존 Employment 재활성화 대신 **새 Employment 생성**을 권장

### 2026-03-18

- 작업자: Cursor
- 작업 목적: Site/Worker import 및 diff 기능 도입, 파일 intake 계층 정비
- 수행 내용(코드 기준)
  - Site master 확장: 계약/금액/건축 정보, 메타(created_by/updated_by) 필드 추가
  - SiteImportBatch 및 `/sites/import` API 구현
  - Person / Employment / WorkerImportBatch 모델 추가
  - `employees_raw.xlsx` / `daily_workers_raw.xls` 기반 worker normalize/import 구현
  - `/workers/import/employees`, `/workers/diff/employees`, `/workers/apply/employees` API 추가
- 테스트
  - backend pytest: 로컬 환경 기준 전체 테스트 통과를 목표로 유지
- 수정 파일(핵심)
  - `backend/app/modules/sites/models.py`
  - `backend/app/modules/sites/routes.py`
  - `backend/app/modules/workers/models.py`
  - `backend/app/modules/workers/service.py`
  - `backend/app/modules/workers/routes.py`
  - `backend/app/core/database.py`
  - `backend/app/main.py`
  - `backend/tests/test_sites_import.py`
  - `backend/tests/test_workers_diff.py`

### 2026-03-17

- 작업자: Cursor
- 작업 목적: BESMA 규정 위반(구조) 수정 및 독립 감사(Auditor) 재검증 반영
- 수행 내용(코드 기준)
  - FK 단일 기준 강제: `DocumentInstance.document_id`(컬럼/relationship) 제거, `Document.instance_id (UNIQUE)`만 유지
  - 승인 API 단일화: `/documents/{id}/submit|approve|reject|resubmit` 제거, `/documents/{id}/review`만 유지
  - workflow 단일 진입점 고정: upload는 `/document-submissions/upload`, review(start_review/approve/reject)는 `/documents/{id}/review`만 사용
  - 상태 분리 유지: `DocumentInstance.status`(오케스트레이션) 미변경, `workflow_status`만 전이
  - 이력 유지: upload/review/approve/reject 시 `DocumentReviewHistory` 기록 유지
- 마이그레이션
  - `backend/alembic/versions/20260317_0004_remove_document_instances_document_id.py` 추가( document_instances.document_id drop )
- 테스트
  - backend pytest: `31 passed`
- 수정 파일(핵심)
  - `backend/app/modules/document_generation/models.py`
  - `backend/app/modules/document_generation/service.py`
  - `backend/app/modules/documents/routes.py`
  - `backend/alembic/versions/20260317_0004_remove_document_instances_document_id.py`
  - `backend/tests/test_document_generation_orchestration.py`

### 2026-03-17

- 작업자: Codex
- 작업 목적: 로그인 CORS 이슈 및 프로젝트 경로 혼선 확인, AI 협업 기준 문서 정리
- 확인 사항
  - 실제 대상 프로젝트는 `D:\besma-rev`
  - `backend/app/main.py`에 CORS 설정 존재
  - `frontend/src/services/api.ts`의 `baseURL`이 `http://127.0.0.1:8001`로 설정됨
  - `GET /health` 엔드포인트 존재
- 생성 파일
  - `docs/ai_collaboration_policy.md`
  - `docs/BESMA_SESSION_STATE.md`
- 수정 파일
  - 없음
- 메모
  - 초기 세션에서 `C:\BESMA`를 보고 잘못 판단한 혼선이 있었음
  - 이후 세션부터는 절대경로 확인을 최우선 체크 항목으로 유지해야 함

## 5. 현재 시스템 상태

### 5.1 백엔드 상태

- 프레임워크: FastAPI
- 실행 명령 기준: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001`
- 상태 판정: 코드 기준 설정 확인 완료, 실행 검증은 세션별 재확인 필요
- 확인 메모
  - CORS 허용 origin에 `5173`, `5174`, `localhost`, `127.0.0.1` 포함
  - `/health` 엔드포인트 존재

### 5.2 프론트 상태

- 프레임워크: Vue 3 + TypeScript + Vite
- 실행 명령 기준: `npm run dev`
- 상태 판정: API baseURL 코드 기준 확인 완료, 실제 브라우저 검증은 세션별 재확인 필요
- 확인 메모
  - API baseURL: `http://127.0.0.1:8001`

### 5.3 로그인 상태

- 현재 판정: 설정상 연결 조건은 맞는 상태
- 남은 확인
  - [ ] 브라우저에서 실제 로그인 시 CORS 오류 미발생 확인
  - [ ] 로그인 성공 후 토큰 저장 및 후속 화면 진입 확인

### 5.4 주요 기능 상태

| 기능 | 상태 | 메모 |
| --- | --- | --- |
| 헬스체크 API | 확인됨 | `GET /health` 존재 |
| 로그인 API 연결 | 코드 확인됨 | 실브라우저 검증 필요 |
| 사용자 인증 | 부분 확인 | JWT 기반으로 추정되며 실제 로그인 검증 필요 |
| 대시보드 진입 | 미확인 | 로그인 이후 동선 점검 필요 |
| 문서 기능 | 미확인 | 후속 테스트 필요 |
| 승인 기능 | 미확인 | 후속 테스트 필요 |

## 6. 문제/버그 트래킹

아래 목록은 열린 이슈 중심으로 유지하고, 해결 시 체크 후 결과를 남긴다.

- [x] 문서 워크플로우 구조 위반(FK/승인 API/진입점) 수정
  - 해결 범위
    - FK 단일 기준: `Document.instance_id (UNIQUE)`만 유지 (`DocumentInstance.document_id` 제거)
    - 승인 API 단일화: `/documents/{id}/review`만 유지
    - workflow 단일 진입점: upload=`/document-submissions/upload`, review=`/documents/{id}/review`
  - 검증: backend pytest `31 passed`

- [ ] 브라우저 로그인 CORS 오류 최종 재현/해결 검증
  - 원인: 과거 보고 기준으로는 프론트 origin과 백엔드 응답 헤더 불일치 의심
  - 현재 상태: 코드상 설정은 정상 확인, 실환경 재검증 필요
  - 관련 파일: `backend/app/main.py`, `frontend/src/services/api.ts`

- [x] 프로젝트 경로 혼동 이슈
  - 원인: `C:\BESMA` 기존 프로젝트와 `D:\besma-rev` 신규 MVP 혼동
  - 현재 상태: 기준 프로젝트를 `D:\besma-rev`로 명시
  - 관련 파일: `docs/ai_collaboration_policy.md`, `docs/BESMA_SESSION_STATE.md`

- [ ] 실제 실행 상태 미확인 이슈
  - 원인: 코드 설정 확인과 실제 프로세스 실행 검증은 별개
  - 현재 상태: 실행 명령과 포트는 확인했으나 세션 내 실행 결과 로그는 누적 필요
  - 관련 파일: `README.md`, `backend/app/main.py`, `frontend/src/services/api.ts`

## 7. 프로젝트 규칙

### 7.1 현재 상태 기준 규칙

- 인증 방식: JWT 기반 로그인
- API baseURL: `http://127.0.0.1:8001`
- DB 종류: SQLite
- 주요 기준 포트
  - backend: `8001`
  - frontend: `5174`

### 7.2 금지사항

- `C:\BESMA`와 `D:\besma-rev`를 같은 프로젝트로 간주하지 않는다.
- 경로와 프레임워크를 확인하지 않은 상태에서 수정하지 않는다.
- 사용자 요청 범위를 벗어난 대규모 리팩터링을 하지 않는다.
- 설정 변경 후 영향 범위를 보고 없이 넘기지 않는다.
- 실행 검증을 하지 않았는데 성공으로 단정하지 않는다.

### 7.3 주의사항

- `README`, `docs/architecture.md`, `docs/mvp_scope.md`, `docs/ai_collaboration_policy.md`를 우선 참조한다.
- backend와 frontend는 포트가 분리되어 있으므로 CORS, baseURL, 인증 흐름을 함께 확인한다.
- 이 파일은 작업 후 반드시 최신 상태로 갱신한다.

### 7.4 세션 변경 시 필수 참조

- 새 세션이 시작되어도 반드시 `docs/ai_collaboration_policy.md`와 `docs/BESMA_SESSION_STATE.md`를 먼저 읽는다.
- `docs/SESSION_START_REQUIRED.md`는 세션 시작용 고정 진입 문서로 사용한다.
- 두 규정을 읽지 않았다면 구현에 착수해서는 안 된다.

### 7.4 외부 조정자(ChatGPT) 인계용 역할

- 이 문서는 내부 세션용 상태 기록일 뿐 아니라, **외부 조정자(ChatGPT)에게 현재 세션을 인계할 때 우선적으로 공유해야 하는 기준 문서**로 사용한다.
- 세션을 ChatGPT에게 넘기거나, ChatGPT를 통해 세션을 다시 이어갈 때 아래 항목을 이 문서에서 발췌하여 전달하는 것을 권장한다.
  - 기준 프로젝트 경로 및 실행 포트(1번, 5번, 7번 항목)
  - 현재 개발 단계와 핵심 목표(2번 항목)
  - 최근 작업 이력(4번 항목 중 최신 항목)
  - 현재 시스템 상태 요약(5번 항목)
  - 열린 문제/버그 목록(6번 항목)
  - 다음 작업 계획(8번 항목)

#### 7.4.1 ChatGPT 인계용 복붙 템플릿

아래 템플릿은 ChatGPT 또는 다른 외부 조정자에게 현재 세션을 인계할 때 복사해서 사용하는 것을 권장하는 양식이다.

```text
[BESMA 인계]
기준 프로젝트:
현재 작업:
방금 한 일:
현재 문제:
다음 작업:
참조 문서:
```

#### 7.4.2 최신 세션 인계본 (2026-03-19)

```text
[BESMA 인계]
기준 프로젝트: D:\besma-rev (FastAPI + Vue3 + SQLite)
현재 작업: SITE context 보정 및 근로자 링크 배포 UX 개선(대규모 현장 운영성 보강) 단계
방금 한 일:
- 테스트 페르소나 SITE_MANAGER에서 site context fallback 선택 기능 반영
- 관리자 화면에서 worker별 access_token/근로자 링크 복사 기능 반영
- site 목록 조회 실패/빈 목록 시 사용자 안내 메시지 보강
- 근로자 직접 진입 시 token 링크 예시 안내 문구 강화
현재 문제:
- 일부 계정(예: hqsafe1)은 실제 site_id가 없어 ping 시 context 선택이 필요
- 대규모 현장(100~200명)에서 worker 링크 수동 복사/전송은 운영 부담이 큼
다음 작업:
- SiteMobileOps에 `전체 근로자 링크 일괄 복사` 버튼 추가
- `이름/토큰/접속링크` CSV 다운로드 기능 추가
- (선택) 향후 문자/카카오 일괄 발송 연동 포인트 설계
참조 문서:
- docs/SESSION_START_REQUIRED.md
- docs/BESMA_SESSION_STATE.md
- docs/ai_collaboration_policy.md
```

## 8. 다음 작업 계획

### 우선순위 1

- [ ] `SiteMobileOpsPage.vue`에 `전체 근로자 링크 일괄 복사` 기능 추가
- [ ] `이름/토큰/근로자 접속링크` CSV 다운로드 기능 추가
- [ ] 100~200명 현장 기준 운영 테스트(배포 -> 링크 전달 -> 진입 -> sign-start/end) 체크리스트 작성

### 우선순위 2

- [ ] `/sites` 조회 실패(401/403/네트워크) 시 라우팅/재로그인 유도 UX 정교화
- [ ] 실제 SITE 계정(`site01/site02`)과 테스트 페르소나 계정 혼용 가이드 문서화
- [ ] 관리자 화면에서 배포별 worker 연락 동선(수기 발송/외부 도구 연계) 표준 안내 문구 반영

### 우선순위 3

- [ ] worker 로그인(계정형) + token 링크(현행) 혼합 모델 전환 필요성 검토
- [ ] 장기적으로 SMS/카카오 일괄 발송 연동 시 보안/만료정책 설계
- [ ] 운영/보안 정책 확정 후 token 만료시간/재발급 정책 문서화

## 9. 작업 후 업데이트 규칙

작업을 마칠 때마다 아래 항목을 반드시 갱신한다.

- [ ] 최근 작업 이력에 오늘 작업 추가
- [ ] 현재 시스템 상태 갱신
- [ ] 해결 또는 신규 버그를 문제/버그 트래킹에 반영
- [ ] 다음 작업 계획 우선순위 조정
- [ ] 경로, 포트, 프레임워크 변경 시 1번 항목 즉시 수정


## 10. AI 협업 규칙

상세 규정은 `docs/ai_collaboration_policy.md`의 `5.X AI 모델 선택 및 능동형 실행 규칙`을 기준으로 한다.

### 10.1 모델 선택 제한 (Cursor)

- 사용 가능 모델: `AUTO`, `GPT-5.4`, `GPT-5.3 Codex`, `Sonnet 4.6`, `Opus 4.6`
- 목록 외 모델 사용 금지 (필요 시 사용자 승인 후 Add Models)
- 모든 작업 프롬프트에 대상 모델 명시

```text
[대상 AI]
Cursor (AUTO)
Cursor (GPT-5.4)
Cursor (GPT-5.3 Codex)
Cursor (Sonnet 4.6)
Cursor (Opus 4.6)
```

### 10.2 기본 선택 기준

- 혼합 구현(백엔드+프론트+설정+테스트): `Cursor (AUTO)` 기본
- 코드 구현/버그/DB/Alembic/테스트: `Cursor (GPT-5.3 Codex)`
- 아키텍처/정책/workflow 설계: `Cursor (GPT-5.4)`
- UI 흐름/간단 프론트 수정: `Cursor (Sonnet 4.6)`
- 고난도 구조 분석/디버깅 방향: `Cursor (Opus 4.6)`

### 10.3 능동 검증 원칙 (강제)

- 실행 전 표준 흐름: `사용자 지시 -> 검증 -> 판단 -> 실행`
- 아래 트리거에서는 즉시 구현 금지 후 검증 수행:
  - 정책/DB/workflow/권한/구조 변경
  - 요청 모호성
  - 기존 기능 영향 가능성
- `Instruction Validation Gate` 미통과 상태에서는 구현 금지
- 사용자 확인 필요 상태/정책 충돌 미해결 상태에서는 구현 금지

### 10.4 검증 출력 형식 (고정)

```text
[Instruction Issue]
- 문제 요약

[충돌 가능성]
- 정책 / invariant / 구조

[리스크]
- 영향 범위

[대안]
- A안
- B안

[권장안]
- 추천 및 이유
```

### 10.5 품질 책임 및 인계

- 모델 선택은 품질을 보장하지 않으며, 모든 결과는 `Invariant Check` 통과가 필수
- 검증 실패 시 모델 교체보다 원인 분석을 우선
- 외부 조정자(ChatGPT)는 모델 선택 추천 가능, Cursor는 실행 주체
- 최종 결정권은 사용자에게 있음

### 10.6 리소스 부족 시 대체 실행 규칙 (5.X+1 요약)

- 발동 트리거:
  - 모델 사용량 초과(Rate limit/quota)
  - 응답 지연/반복 실패
  - 특정 모델 선택 불가
  - Cursor 내부 실행 불안정
- 우선순위:
  1. `Cursor` 내 다른 모델 전환
  2. `Cursor (AUTO)` 재시도
  3. `VS Code Codex` 전환
- `VS Code Codex` 전환 시 동일 프롬프트/동일 작업 범위/동일 규정 유지
  - `Instruction Validation Gate` 적용
  - `Invariant Check` 적용
  - 동일 보고 형식 유지
- 금지:
  - 무작정 모델 반복 시도
  - 규정 없이 VS Code Codex 단독 사용
  - 검증 절차 생략
  - 결과 비교 없는 혼합 반영
- 결과 검증:
  - Cursor 기준 규정으로 재검증
  - Invariant Check 수행
  - 기존 코드 충돌 여부 확인
- 복귀 원칙:
  - Cursor 정상화 즉시 Cursor로 복귀
- 책임 원칙:
  - 대체 실행 결과도 품질/검증/보고 책임 동일 유지
