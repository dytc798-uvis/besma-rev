# BESMA 프로젝트 상태·진행 참조 (루트 스냅샷)

> **목적**: 에이전트·개발자가 저장소 루트에서 바로 열어 **현재 제품 상태**, **병목**, **충돌/주의**, **다음 추천 방향**을 확인한다.  
> **갱신**: 구조·메뉴·라우팅·주요 병목이 바뀔 때 수동으로 이 파일을 업데이트한다. (정본 규칙은 여전히 `docs/` 아래 문서.)

**기준일**: 2026-04-16

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

### 1.2 그대로 둔 경계

- **위험성평가 DB** (`/site/risk-library`, `RiskLibraryPage`)는 **참조 DB**로 유지. 위 허브와 **통합 대상 아님**.
- 문서·제출 API 경로·`meta.uiType` 패턴은 `docs/ARCHITECTURE_INVARIANTS.md` 준수.

---

## 2. 앞으로의 진행 추천 방향

| 우선순위 | 방향 | 비고 |
|----------|------|------|
| 높음 | **미결정(OPEN) 소화** | `docs/OPEN_DECISIONS.md`의 KPI·기한 표현·SITE 문서 기본 뷰 등은 구현 전 오너 선택 필요. |
| 높음 | **회귀 확인** | `/site/mobile`, `/site/mobile/daily-capture`, 소통·현장 검색, 로그인 후 SITE 홈 리다이렉트(넓은/좁은 창). |
| 중간 | **프론트 번들** | Vite 빌드 시 메인 청크 500kB+ 경고 — 필요 시 `manualChunks` 등 점진적 분할 검토. |
| 중간 | **문서·온보딩 카피** | 사용자 가이드·스크린샷에 예전 명칭(「모바일 운영」「TBM·일지」 등)이 남아 있으면 허브 명칭에 맞게 정리. |
| 낮음(별도 결정) | 허브 **기본 탭** 정책 | 현재는 모바일 폭에서 일지 우선; 현장 정책이 바뀌면 `siteHomeRoute`만 조정하면 됨(제품 결정 후). |

구현 시 **항상** 다음 순서로 읽기: `docs/DECISION_LOG.md` → `docs/ARCHITECTURE_INVARIANTS.md` → `docs/OPEN_DECISIONS.md` (프로젝트 규칙).

---

## 3. 현재 병목·제약

| 구분 | 내용 |
|------|------|
| **제품 결정** | `OPEN-001`~`OPEN-003` 등: KPI 구성, 기한/지연 표현, SITE 문서 화면 기본 뷰 등 **코드로 임의 확정 불가**. |
| **데이터 모델** | 요구사항 행에 **항목별 마감 일시** 없음 → “기한 초과 건수” 정밀 집계 불가 (`due_rule_text` 수준). INVARIANT Rule 11. |
| **상태 코드** | `REJECTED` 등 API `status` 집합 고정. 프론트에서 임의 코드값 추가 시 서버와 불일치. |
| **개발 환경** | 일부 터미널/프로필에서 `Set-Location` 경로 오류 로그가 보일 수 있음 — 빌드 자체는 통과 가능. |
| **테스트** | E2E(브라우저) 자동 검증은 이 저장소 스냅샷에 전제되지 않음; 수동 스모크 권장. |

---

## 4. 현재 기능과 충돌·주의 정보

| 주제 | 설명 |
|------|------|
| **INVARIANT vs. 카피** | Rule 15 등 문서에는 여전히 「모바일 운영」 표현이 있을 수 있음 — **의미는 SITE 실행 허브**로 이해. UI 라벨은 「일일안전회의(일일위험성평가)」로 통일된 상태. |
| **딥링크** | `/site/mobile/daily-capture` URL은 유지. 북마크·알림 링크 깨지지 않음. |
| **라우트 이름** | `next({ name: 'site-mobile-ops' })` 등 기존 `name` 유지. 셸 도입으로 **부모–자식** 구조만 변경됨. |
| **활성 메뉴** | 사이드바 「일일안전회의(일일위험성평가)」는 `site-mobile-ops` **와** `site-mobile-daily-capture` 에서 동시에 활성으로 표시(의도된 동작). `communications` / `site-search` 에서는 비활성. |
| **위험성평가 명칭** | 메뉴에 「위험성평가 DB」와 허브 탭 「위험성평가」가 공존 — **DB 조회** vs **일일 작업계획·채택** 맥락이 다름. 사용자 혼동 시 카피만 보강(구조 변경 불필요). |
| **Decision Trigger** | UI 구조·KPI·정렬·상태 문구·흐름을 바꾸는 작업은 `.cursor/rules` 및 `OPEN_DECISIONS.md` 절차 준수. |

---

## 5. 관련 파일 (빠른 점프)

| 역할 | 경로 |
|------|------|
| 허브 셸·탭 | `frontend/src/layouts/SiteDailySafetyShellLayout.vue` |
| SITE 사이드바·모바일 드로어 | `frontend/src/layouts/SiteLayout.vue` |
| 라우트 정의 | `frontend/src/router/index.ts` |
| 모바일/데스크톱 홈 라우트 이름 | `frontend/src/utils/siteHomeRoute.ts` |
| 운영 페이지 | `frontend/src/pages/site/SiteMobileOpsPage.vue` |
| 일지·사진 페이지 | `frontend/src/pages/site/SiteMobileDailyCapturePage.vue` |
| HQ 메뉴 순서 라벨 | `frontend/src/pages/hq/HQDocumentSettingsPage.vue` (`FIXED_MENU_LABELS.SITE`) |

---

## 6. 변경 이력 (이 문서)

| 날짜 | 내용 |
|------|------|
| 2026-04-16 | 초안: 일일안전회의 허브 통합·반응형·OPEN/INVARIANT 연계·병목·충돌 표 정리. |
