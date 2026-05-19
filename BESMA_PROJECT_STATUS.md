# BESMA 프로젝트 상태·진행 참조 (루트 스냅샷)

> **목적**: 에이전트·개발자가 저장소 루트에서 바로 열어 **현재 제품 상태**, **병목**, **충돌/주의**, **다음 추천 방향**을 확인한다.  
> **갱신**: 구조·메뉴·라우팅·주요 병목이 바뀔 때 수동으로 이 파일을 업데이트한다. (정본 규칙은 여전히 `docs/` 아래 문서.)

**기준일**: 2026-05-20

---

## 1. 현재 상태 (요약)

### 1.1 현장(SITE) — 일일안전회의·일일 위험성평가 허브

- **메뉴 명칭**: 사이드바 단일 항목 **「일일안전회의(일일위험성평가)」** → `/site/mobile`.
- **라우팅**: `SiteDailySafetyShellLayout` 부모 아래 중첩 라우트.
  - `''` → `site-mobile-ops` (`SiteMobileOpsPage`) — 작업계획·TBM·위험 채택 등 운영 화면.
  - `daily-capture` → `site-mobile-daily-capture` (`SiteMobileDailyCapturePage`) — 일지·사진·PDF 업로드.
  - `communications`, `site-search` — 허브 **탭 없음** (이름·경로 유지).
- **허브 탭**: ops / daily-capture 에서만 상단 탭 표시 (작업계획·TBM·위험성평가 / 일지·사진·문서).
- **기본 진입**: `frontend/src/utils/siteHomeRoute.ts` — 뷰포트 **≤768px** 는 일지 탭, **그 외** 는 운영 탭 (`siteMobileOrDesktopHomeName()`).
- **반응형**: 허브 탭·운영 페이지 헤더 버튼·사이드 메뉴 긴 라벨 줄바꿈 등 **768px** 기준을 `SiteLayout`과 맞춤.

### 1.2 SITE 문서취합 (`/site/documents`)

- **3영역 구조** ([DECISION-053], [OPEN-042] 해결): `현재 작업` / `재조치 필요` / `주기·기타` (+ 본사 점검표 확인).
- **이력 API**: `GET /documents/history`는 **`site_id` + `requirement_id`만** 사용. SITE는 **업로드 이력(`DocumentUploadHistory`)만** 반환(문서-only 폴백 병합 없음). 타 현장 `site_id`는 403.
- **오업로드 수정**: [DECISION-065] 파일 교체형 — `현재 작업`·`주기·기타`에 `수정` 버튼; `재조치`는 반려 건에 `수정 업로드`·파일 교체 `수정`(동일 `site_id` 인스턴스).

### 1.3 현장 canonical·데모 (Alembic 0051 / 0052)

- **0051**: `site03` 등 데모 스텁을 운영 canonical 현장(예: 청라 C18)으로 사용자·연결 정리(idempotent).
- **0052**: 사용자별 데모 스텁 → canonical **배치 리맵**(`_alembic_site_remap_batch_0052` 기록, downgrade 지원). **재실행 안전(idempotent)**.
- **운영 반영**: EC2에서 `alembic upgrade head` 시 0051→0052→0053 순 적용. `reset_demo`·전체 seed 재실행은 운영 금지.

### 1.4 ADHOC 메뉴·요구사항 (0053)

- **마이그레이션 `20260514_0053`**: 근로자 의견청취 등 **ADHOC(수시) 요구사항**·SITE 메뉴 노출 정책 반영(시드/설정과 정합).
- **배포 기준**: `origin/main` **bc61289** (0053 포함) — EC2+Vercel 2단계 배포 완료 상태.

### 1.5 그대로 둔 경계

- **위험성평가 DB** (`/site/risk-library`, `RiskLibraryPage`)는 **참조 DB**로 유지. 위 허브와 **통합 대상 아님**.
- 문서·제출 API 경로·`meta.uiType` 패턴은 `docs/ARCHITECTURE_INVARIANTS.md` 준수.

---

## 2. 앞으로의 진행 추천 방향

| 우선순위 | 방향 | 비고 |
|----------|------|------|
| 높음 | **미결정(OPEN) 소화** | `OPEN-001`/`002`는 DECISION-008과 동기화됨(HQ KPI·기한). `OPEN-050` 등 주기별 동시 노출은 별도. |
| 높음 | **회귀 확인** | `/site/mobile`, `/site/documents` 3영역·이력 모달, 로그인 후 SITE 홈 리다이렉트. |
| 중간 | **프론트 번들** | Vite 빌드 시 메인 청크 500kB+ 경고 — 필요 시 `manualChunks` 등 점진적 분할 검토. |
| 중간 | **문서·온보딩 카피** | 사용자 가이드·스크린샷에 예전 명칭이 남아 있으면 허브·문서취합 3영역에 맞게 정리. |
| 낮음(별도 결정) | 허브 **기본 탭** 정책 | 현재는 모바일 폭에서 일지 우선; 현장 정책이 바뀌면 `siteHomeRoute`만 조정. |

구현 시 **항상** 다음 순서로 읽기: `docs/DECISION_LOG.md` → `docs/ARCHITECTURE_INVARIANTS.md` → `docs/OPEN_DECISIONS.md`.

---

## 3. 현재 병목·제약

| 구분 | 내용 |
|------|------|
| **제품 결정** | `OPEN-001`/`002`(HQ 외·기한 표현), `OPEN-004`~`007`, `OPEN-050` 등 — **코드로 임의 확정 불가**. |
| **데이터 모델** | 요구사항 행에 **항목별 마감 일시** 없음 → “기한 초과 건수” 정밀 집계 불가. HQ는 [DECISION-008] 4 KPI만. |
| **상태 코드** | `REJECTED` 등 API `status` 집합 고정. 프론트에서 임의 코드값 추가 시 서버와 불일치. |
| **개발 환경** | 일부 터미널/프로필에서 `Set-Location` 경로 오류 로그가 보일 수 있음 — 빌드 자체는 통과 가능. |
| **테스트** | E2E(브라우저) 자동 검증은 이 저장소 스냅샷에 전제되지 않음; 수동 스모크 권장. |

---

## 4. 현재 기능과 충돌·주의 정보

| 주제 | 설명 |
|------|------|
| **INVARIANT vs. 카피** | Rule 15 등에 「모바일 운영」 표현이 남을 수 있음 — **의미는 SITE 실행 허브**. UI 라벨은 「일일안전회의(일일위험성평가)」. |
| **딥링크** | `/site/mobile/daily-capture` URL 유지. |
| **문서 이력** | SITE에서 Document만 있고 UploadHistory 없으면 **빈 목록**(HQ document fallback 없음). |
| **위험성평가 명칭** | 「위험성평가 DB」 vs 허브 탭 「위험성평가」 — 맥락이 다름. |
| **Decision Trigger** | UI 구조·KPI·정렬·상태 문구·흐름 변경 시 `.cursor/rules` 및 `OPEN_DECISIONS.md` 절차 준수. |

---

## 5. 관련 파일 (빠른 점프)

| 역할 | 경로 |
|------|------|
| 허브 셸·탭 | `frontend/src/layouts/SiteDailySafetyShellLayout.vue` |
| SITE 사이드바·모바일 드로어 | `frontend/src/layouts/SiteLayout.vue` |
| SITE 문서취합 3영역 | `frontend/src/pages/site/SiteDocumentsDashboardPage.vue` |
| 라우트 정의 | `frontend/src/router/index.ts` |
| 문서 이력 API | `backend/app/modules/documents/routes.py` |
| SITE 리맵 0052 | `backend/alembic/versions/20260514_0052_site_demo_stub_to_canonical_per_user.py` |
| 모바일/데스크톱 홈 | `frontend/src/utils/siteHomeRoute.ts` |

---

## 6. 운영 서버 배포 (요약)

| 항목 | 내용 |
|------|------|
| **표준 흐름** | (필요 시) 안전 범위 **커밋** → **`git push origin main`** → **`deploy/deploy_all.ps1`** (EC2 pull + `deploy_backend.sh` + `systemctl restart besma-backend`) → **`deploy/deploy_frontend_vercel.ps1`** (Vercel). |
| **백엔드** | SSH로 원격 `git pull`; 스크립트 로그 **`[deploy] Remote HEAD after pull:`** 로 실제 반영 SHA 확인. |
| **프론트** | API만 EC2; 정적 UI는 **Vercel** (`www.besma.co.kr`). 백엔드 스크립트만으로는 UI가 갱신되지 않음. |
| **deploy_all 가드** | 기본: **깨끗한 작업 트리** + push 포함. `-AllowDirtyWorkingTree`, `-SkipPush`, `-AllowSkipPushUnpushed`, `-SkipFrontendBuild`, `-RemoteGitCleanUntracked`(EC2 `alembic/versions` 미추적만 정리)는 예외. |
| **금지 커밋** | `*.pem`, `.env` 실비밀, `storage/` 대용량, `node_modules` 등 — `docs/OPERATIONS_DEPLOY.md` 「배포 트리 위생」 참고. |
| **키·호스트** | `deploy/BACKEND_OPERATIONS.md`, 루트 `.env`의 `BESMA_SSH_KEY_PATH`. |

---

## 7. 변경 이력 (이 문서)

| 날짜 | 내용 |
|------|------|
| 2026-04-16 | 초안: 일일안전회의 허브 통합·반응형·OPEN/INVARIANT 연계·병목·충돌 표 정리. |
| 2026-04-16 | §6 추가: 운영 배포·프론트 분리 안내. |
| 2026-05-20 | SITE 3영역·이력 site_id-only·0051/0052 canonical·0053 ADHOC·2단계 배포·deploy_all 가드 반영. |
