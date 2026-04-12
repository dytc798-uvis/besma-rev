# BESMA 결정 로그 (Decision Log)

이 문서는 **확정된 개발·제품 의사결정**만 기록한다.  
여기에 적힌 결정은 **임의로 뒤집지 않는다**. 변경이 필요하면 **새 Decision ID**로 “폐기/대체”를 명시해야 한다.

---

## Cursor / 협업 도구 운영 규칙 (필수)

1. **작업 시작 전** 이 파일(`DECISION_LOG.md`)과 `ARCHITECTURE_INVARIANTS.md`를 읽는다.
2. **기존 결정과 충돌하는 제안**이 필요하면, 코드를 바꾸지 말고 **사용자(오너)에게 보고**하고 지시를 받는다.
3. **새로 설계가 필요한 선택지**가 있으면 `OPEN_DECISIONS.md`에 항목을 추가하거나, 기존 OPEN을 갱신한다.
4. **사용자가 A/B 중 선택**하면, 그 결과를 본 문서에 **새 DECISION 항목으로 반드시 기록**한다.

---

## 결정 목록

### [DECISION-001]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | UI 타입은 HQ_SAFE / SITE / HQ_OTHER 세 가지로 고정 |
| **Context** | 본사 안전, 현장, 본사 타부서 등 역할이 나뉘어 있으며 라우터·레이아웃이 이에 맞춰 있다. |
| **Options** | A. UI 타입 추가 (예: 전용 안전 플랫폼 셸) / B. 기존 3타입 유지 |
| **Decision** | **B** — 세 타입만 사용한다. |
| **Reason** | 라우트·권한·화면 분기가 이미 `meta.uiType` 등에 묶여 있으며, 분기 증가는 회귀 비용이 크다. |
| **Impact Scope** | `frontend/src/router/index.ts`, `frontend/src/layouts/HQSafeLayout.vue`, `SiteLayout.vue`, `HQOtherLayout.vue`, 인증 후 리다이렉트 로직 |

---

### [DECISION-002]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | `safety_platform` 등 문서·TBM 흐름과 분리된 신규 도메인을 만들지 않는다 |
| **Context** | 별도 “임시 안전보건 플랫폼(요청→검토→조치→검증)” 설계가 문서로만 존재할 수 있으나, 코드베이스에는 반영하지 않기로 했다. |
| **Options** | A. 신규 모듈·라우트군(`/safety-platform` 등) 추가 / B. 기존 BESMA 축 안에서만 확장 |
| **Decision** | **B** |
| **Reason** | API·라우트·데이터 모델이 이미 문서/현장/의견/TBM 등에 연결되어 있으며, 병렬 세계관은 유지보수와 권한 혼선을 키운다. |
| **Impact Scope** | 백엔드 `app/modules/*` 신규 최상위 도메인 추가 금지 원칙, 프론트 병렬 사이드바 금지 |

---

### [DECISION-003]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | 문서 관련 공개 API 경로는 `/documents/*` 및 `/document-submissions/*`를 유지한다 |
| **Context** | 문서 목록·취합 대시보드·업로드·검토가 해당 경로에 연결되어 있다. |
| **Options** | A. REST 경로 재설계 / B. 기존 경로 유지 |
| **Decision** | **B** |
| **Reason** | 프론트·테스트·외부 스크립트가 경로에 의존한다. |
| **Impact Scope** | `backend/app/modules/documents/routes.py`, `document_submissions`, `document_generation` 호출부, `frontend/src/services/api.ts` 사용처 |

---

### [DECISION-004]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | 본사 문서 취합·현장 문서 화면의 라우트 경로를 유지한다 |
| **Context** | 운영자가 북마크·교육 자료로 경로를 사용 중일 수 있다. |
| **Options** | A. `/hq-safe/documents`, `/site/documents` 변경 / B. 유지 |
| **Decision** | **B** |
| **Reason** | “구조 고정” 우선; 개선은 동일 경로 내 UI·구성으로만 한다. |
| **Impact Scope** | `HQDocumentsDashboardPage.vue`, `SiteDocumentsDashboardPage.vue`를 가리키는 모든 링크 |

---

### [DECISION-005]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | 요구사항(문서 의무) 상태값은 백엔드가 정의한 문자열을 “진실의 원천”으로 한다 |
| **Context** | `get_site_requirement_status`가 행마다 `status`를 내려준다. |
| **Options** | A. 프론트에서 임의로 새 상태코드 발명 / B. API 값 + 표시 라벨만 통일 |
| **Decision** | **B** |
| **Reason** | 스키마·집계 로직과 불일치하면 숫자·정렬이 어긋난다. |
| **Impact Scope** | 문서 취합·현장 대시보드·배지; 자세한 목록은 `ARCHITECTURE_INVARIANTS.md` |

---

### [DECISION-006]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | 제품 설명상 “문서 취합”을 운영 허브(중앙)로 둔다 — 단, API 분기 신설 없음 |
| **Context** | 결재·TBM·현장·사용자 기능이 있으나, 미제출·반려·검토 큐는 문서 요구사항 흐름과 연동된다. |
| **Options** | A. 문서 취합을 단순 조회 기능으로만 둔다 / B. 운영 의사결정의 중심 화면으로 삼되 구현은 기존 API 범위 내 / C. 신규 백엔드 허브 API 추가 |
| **Decision** | **B** (C는 별도 결정·범위 없이 진행하지 않음) |
| **Reason** | 오너 방향은 “중심”이나, DECISION-003과 충돌하는 백엔드 확장은 이번 단계에서 하지 않는다. |
| **Impact Scope** | 우선순위·카피·섹션 구성 등 **프론트 표현**; `OPEN_DECISIONS.md`의 미결 KPI·기한 표현 |

---

### [DECISION-007]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | 사이드바의 “설정·현장 정보” 등 placeholder 링크는 라우트가 생기기 전까지 구조적 결함으로 관리한다 |
| **Context** | 레이아웃에 링크는 있으나 `router/index.ts`에 대응 child가 없다. |
| **Options** | A. 방치 / B. 라우트 추가 또는 링크 제거로 정합성 맞춤 |
| **Decision** | **B** 필요 — 구체 실행은 OPEN 또는 별 태스크에서 선택 |
| **Reason** | 죽은 링크는 운영 신뢰를 깨뜨린다. |
| **Impact Scope** | `HQSafeLayout.vue`, `SiteLayout.vue`, `HQOtherLayout.vue`, `router/index.ts` (실행 시에만) |

---

### [DECISION-008]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | HQ 문서취합 화면은 운영 우선순위 기준으로 고정 |
| **Context** | 기존 HQ 문서취합 화면은 데이터 조회 중심 구조였고, 운영자가 무엇을 먼저 처리해야 하는지 명확하지 않았다. |
| **Options** | A. KPI·정렬·필터를 화면별로 자유 구성 / B. 운영 우선순위에 맞춘 KPI·정렬·기본 필터를 **불변 규칙**으로 고정 |
| **Decision** | **B** — 아래 「불변 규칙」 전체를 **강제 실행 수준**으로 적용한다. (권장이 아님. 이후 변경·예외 없음.) |
| **Decision — KPI (고정)** | 문서취합 HQ 화면의 KPI는 **아래 4개만** 사용한다. 추가·삭제·명칭·의미 변경 금지: (1) 미제출 `NOT_SUBMITTED` (2) 반려 `REJECTED` — 재업로드 필요로 해석 (3) 검토중 `IN_REVIEW` (4) 전체 제출 대상 `total_required`. |
| **Decision — 테이블 기본 정렬 (고정)** | 요구사항(행) 기준 테이블의 **기본 정렬 우선순위**는 아래 순서다. 이 순서를 깨는 “기본 뷰” 금지: 1) `REJECTED` 2) `NOT_SUBMITTED` 3) `IN_REVIEW` 4) `SUBMITTED` 5) `APPROVED` 6) `NOT_REQUIRED`. |
| **Decision — 기본 필터 (고정)** | `NOT_REQUIRED`는 **기본 숨김**. `APPROVED`는 위 정렬 규칙에 따라 **하단**에 모인다. (사용자가 필터로 다시 보이게 하는 것은 허용하되, **초기 진입 시 기본값**은 본 규칙을 따른다.) |
| **Reason** | 운영 우선순위가 화면에 직접 반영되어야 하며, 사용자가 “판단”이 아니라 “처리”를 하게 만들어야 한다. |
| **Impact Scope** | `frontend/src/pages/**/HQDocumentsDashboardPage.vue`, `frontend/src/components/**/DocumentTable.vue` 및 동일 역할의 표·KPI 영역 전부 |

---

### [DECISION-009]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | SITE 문서 화면은 작업 리스트 중심으로 고정 |
| **Context** | 기존 SITE 화면은 전체 목록 + 업로드 UI 중심이었고, 현장 사용자가 “무엇을 해야 하는지” 판단하기 어려웠다. |
| **Options** | A. 전체 목록·조회를 기본 화면으로 유지 / B. “할 일 목록”을 기본 화면으로 고정하고 조회는 보조 |
| **Decision** | **B** — 아래 「불변 규칙」 전체를 **강제 실행 수준**으로 적용한다. |
| **Decision — 기본 화면** | 기본 화면은 전체 목록이 아니라 **“할 일 목록”(작업 큐)** 이다. |
| **Decision — 기본 표시 대상** | 기본으로 반드시 포함하는 상태: `NOT_SUBMITTED`, `REJECTED`, `IN_REVIEW`. |
| **Decision — 기본 숨김** | 기본으로 숨기는 상태: `APPROVED`, `NOT_REQUIRED`. (필터·탭 등으로 노출하는 것은 허용하되 **첫 화면 기본값**은 숨김.) |
| **Decision — 상단 영역** | 상단 영역(요약·카드·안내 등)은 반드시 **“오늘 해야 할 일”** 기준으로 구성한다. (단순 전체 건수 나열을 기본 상단의 목적으로 하지 않는다.) |
| **Reason** | 현장은 조회가 아니라 실행이 목적이며, 작업 대상만 보여야 한다. |
| **Impact Scope** | `frontend/src/pages/**/SiteDocumentsDashboardPage.vue` 및 동일 경로·역할의 SITE 문서 대시보드 전부 |

---

### [DECISION-010]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-20 |
| **Title** | REJECTED 상태는 재조치 필요로 UI 통합 |
| **Context** | `REJECTED`는 실제로 재업로드·재조치가 필요한 상태이나, 별도 상태를 만들면 API·집계와 불일치가 난다. |
| **Options** | A. `REWORK`, `NEED_ACTION` 등 신규 상태·코드·라벨 체계 도입 / B. 시스템 상태는 `REJECTED`만 유지하고 UI 라벨만 통일 |
| **Decision** | **B** — 아래 「불변 규칙」 전체를 **강제 실행 수준**으로 적용한다. |
| **Decision — 시스템 상태** | 백엔드·API·데이터에서 쓰는 상태 문자열은 **`REJECTED`만** 유지한다. |
| **Decision — UI 표시** | 사용자에게 보이는 문구는 반드시 **「반려 (재업로드 필요)」** 로 통일한다. (동일 의미의 다른 카피로 바꾸지 않는다.) |
| **Decision — 금지** | 프론트·문서·기획 어디에서도 **`REWORK`**, **`NEED_ACTION`**, 그 밖의 “재조치 필요”를 나타내는 **별도 상태코드·상태명 추가 금지**. |
| **Reason** | 데이터 구조와 UI 의미를 일치시키고, 상태 확장으로 인한 구조 붕괴를 방지한다. |
| **Impact Scope** | `frontend/src/components/**/StatusBadge.vue`, 모든 문서 요구사항·제출 상태 표시 영역(테이블 셀, 카드, 필터 라벨 등) |

---

### [DECISION-011]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-25 |
| **Title** | 도급사그룹별 문서항목묶음 적용은 런타임 계산, 삼성은 파일럿 점수/요구사항 오버라이드 |
| **Context** | 도급사(상위/하도급 구분 포함)의 문서취합 기준을 커스터마이징하기 위해 도급사별(도급사그룹별) 문서항목묶음이 필요합니다. 또한 삼성물산/삼성E&A는 매핑 없이 고정 파일럿현장 기준으로 처리하되, 일단 화성기아현장만 지정하고(현장명은 유지), 점수/요구사항 계산에서만 삼성 기준으로 오버라이드합니다. 삼성 제외 현장은 일반(기존 수준) 규칙을 사용합니다. |
| **Options** | A. 런타임 계산 / B. pre-expansion(그룹 변경 시 `document_requirements` 갱신) / C. hybrid(그룹 소스 + 캐시 혼합) |
| **Decision** | **A** |
| **Reason** | 파일럿현장 교체는 `pilot` 자체만 바꾸면 되도록 설계해야 하고, 삼성 제외 현장은 회귀 없이 기존 계산을 유지해야 하므로 런타임 적용이 적합합니다. |
| **Impact Scope** | `backend/app/modules/documents/service.py`의 `get_site_requirement_status`(도급사그룹 규칙 적용 + 삼성 파일럿 오버라이드 계산) 및 `frontend/src/pages/hq/HQDocumentsDashboardPage.vue`에서 도급사 선택이 문서취합 계산에 반영되는 경로 |

---

### [DECISION-012]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-25 |
| **Title** | 도급사 선택/그룹 규칙(전역 유지 + 1개 그룹)과 문서항목 수정 범위 |
| **Context** | 도급사는 전사적으로 선택하며 팀을 전환해도 선택 상태가 유지됩니다. 도급사는 1개 그룹만 가집니다. 또한 도급사그룹별 문서항목 묶음을 설정할 때, 미지정 fallback은 전체 기본을 사용하며 문서항목은 추가/제거/수정이 가능하고 수정 범위는 `DocumentRequirement` 주요 필드까지 포함합니다(`is_required`, `frequency`, `due_rule_text`, `note`, `display_order`). |
| **Options** | A. 포함/제거 + 정렬만 수정 / B. `DocumentRequirement` 주요 필드까지 수정 가능 / C. 복수 그룹 가능(충돌 규칙 필요) |
| **Decision** | **B** |
| **Reason** | 향후 도급사별 다른 기준(상위/하도급, 도급사별 정책)을 준비하려면 “수정”의 범위를 데이터 모델 레벨까지 열어두는 것이 안전합니다. |
| **Impact Scope** | `backend/app/modules/document_settings/routes.py`(도급사그룹/문서항목 묶음 저장/검증), `frontend/src/pages/hq/HQDocumentSettingsPage.vue`(도급사/그룹/문서항목 묶음 편집 UI) |

---

### [DECISION-013]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-25 |
| **Title** | 삼성물산/삼성E&A 도급사 버튼은 4팀에서만 표시 |
| **Context** | 삼성물산/삼성E&A는 요청대로 특별케이스로 처리하며, 도급사 버튼의 표시 범위를 4팀 중심으로 고정해 초기 운영 혼선을 줄입니다. |
| **Options** | A. 모든 팀에서 표시 / B. 4팀에서만 표시 / C. 팀별 설정으로 표시 범위 분리 |
| **Decision** | **B** |
| **Reason** | 초기 파일럿 운영 범위를 명확히 하고 UI 학습 비용을 최소화합니다. |
| **Impact Scope** | (추후 구현) `HQDocumentSettingsPage.vue`에서 도급사 버튼 표시 팀 범위 로직 |

---

### [DECISION-014]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-25 |
| **Title** | 삼성 파일럿현장 계산은 삼성 도급사(또는 삼성 그룹) 설정이 있으면 반영 |
| **Context** | 삼성 파일럿현장은 “항상 삼성 기본”으로만 계산하지 않고, 사용자가 설정한 삼성 도급사(또는 삼성 그룹) 기준이 존재하면 그 설정을 반영해 계산해야 합니다. |
| **Options** | A. 항상 삼성 기본 / B. 삼성 설정 존재 시 반영 / C. 선택 상태에 따라 계산 달라짐 |
| **Decision** | **B** |
| **Reason** | 추후 커스터마이징 확장과의 정합성을 유지하면서 MVP에서는 “설정 존재 여부” 기준으로 예측 가능하게 동작시키기 위함입니다. |
| **Impact Scope** | (추후 구현) `backend/app/modules/documents/service.py`에서 삼성 파일럿 오버라이드 적용 기준 |

---

### [DECISION-015]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-25 |
| **Title** | `문서항목 수정`은 도급사별 문서항목 설정 페이지로 라우팅 |
| **Context** | HQ 대시보드에서 “현장명 검색 왼쪽의 문서항목 수정” 버튼을 눌렀을 때, 도급사별 커스터마이징 흐름으로 자연스럽게 진입해야 합니다. |
| **Options** | A. HQ 모달 / B. 별도 페이지 라우팅(컨텍스트 query/스토어) / C. 기존 설정 페이지 내부 탭 |
| **Decision** | **B** |
| **Reason** | UI 복잡도를 분리해 유지보수성을 확보하고, 선택 컨텍스트 전달을 명확히 하기 위함입니다. |
| **Impact Scope** | (추후 구현) `frontend/src/pages/hq/HQDocumentsDashboardPage.vue`의 버튼 처리 + 라우팅/컨텍스트 전달 로직 |

---

### [DECISION-016]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-25 |
| **Title** | 삼성 전용 그룹은 1개만 사용, 나머지는 일반 그룹으로 처리 |
| **Context** | 요청 확정: 삼성물산/삼성E&A는 특별케이스로 파일럿현장(화성기아)에서 삼성 기준을 적용하되, 삼성 전용 그룹은 1개만 만들고 나머지는 우선 일반 그룹(현행 수준)으로 간주합니다. |
| **Options** | A. 삼성 파일럿은 항상 삼성 전용 그룹(1개) 적용, 일반은 기존 계산 유지 / B. 삼성 파일럿도 사용자 선택에 따라 삼성/일반 동적 전환 / C. 삼성/일반 모두 그룹별 요구사항 세트를 분리 저장해 일관 적용 |
| **Decision** | **A** |
| **Reason** | “삼성 파일럿현장만 별도 계산, 나머지는 지금 수준”을 MVP에서 최소 변경으로 만족하기 위해서입니다. |
| **Impact Scope** | `backend/app/modules/documents/service.py`의 `get_site_requirement_status` 계산 분기(삼성 파일럿 -> 삼성 전용 그룹 1개, 그 외 -> 기존 현행 로직) |

---

### [DECISION-017]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-25 |
| **Title** | `안전문서 설정관리`에서 문서유형 표시 최소화(파일명(code) 중심) |
| **Context** | `HQDocumentSettingsPage`에서 문서유형명(예: 일상점검/법정서류/점검/의견관련/예산/사고/기타)이 운영상 무의미하므로, DB/화면 구조는 유지하되 표시를 줄이고 “파일 이름”처럼 문서 코드 중심으로만 보이게 해야 함. |
| **Options** | A. 문서유형 자체(마스터/DB 의미)를 숨기고 요구사항 중심 별도 관리 화면으로 전환 / B. DB/화면 구조는 유지하고 UI 표시만 “그룹/카피”를 줄여 `DocumentTypeMaster.code` 중심으로 표시 / C. 지정된 문서유형만 필터링(표시 제거) |
| **Decision** | **B** |
| **Reason** | 표시 변경만으로 사용자가 원하는 “파일명(code/title 느낌)” 가시성을 즉시 확보하고, 구조/데이터 의미 변경에 따른 회귀 위험을 최소화하기 위해서입니다. |
| **Impact Scope** | `frontend/src/pages/hq/HQDocumentSettingsPage.vue`의 목록 row 표시(문서유형명 제거) + 검색/정렬 기준(이름 대신 코드 중심) 조정 |

---

### [DECISION-018]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-25 |
| **Title** | 최초 로그인 비밀번호 변경 강제(접근 차단) 정책 |
| **Context** | 초기 1회성 비밀번호를 사용한 신규/초기화된 계정은 비밀번호 변경 완료 전까지 모든 서비스 접근을 차단해야 함. 로그인 성공 시 클라이언트가 `change-password` 화면으로 이동하도록 하고, 백엔드 인증 의존성 레벨에서 `PASSWORD_CHANGE_REQUIRED`로 403 차단을 보장해야 함. |
| **Options** | A. `users.must_change_password` 플래그로 강제 차단하며 `GET /auth/me`, `/auth/change-password`, `/auth/logout`는 예외 / B. 프론트에서만 리다이렉트하고 백엔드는 허용 / C. 롤/화면별 부분 차단 |
| **Decision** | **A** |
| **Reason** | UX(리다이렉트)와 보안(서버 차단)을 동시에 보장해야 하며, 예외 경로를 제한해 회귀 위험을 줄이기 위함. |
| **Impact Scope** | `backend/app/modules/auth/routes.py`, `backend/app/core/auth.py`, `backend/app/modules/users/models.py`, `backend/app/schemas/auth.py`, Alembic users 스키마 변경, `frontend/src/stores/auth.ts`, `frontend/src/router/index.ts`, `frontend/src/pages/auth/ChangePasswordPage.vue`(신규) 및 `frontend/src/pages/LoginPage.vue`(리다이렉트 보강) |

---

### [DECISION-019]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-26 |
| **Title** | 직원(employees_raw) 부서코드 기준 본사/비본사 구분 |
| **Context** | `docs/sample/site_import/raw` 등에서 내려오는 직원 엑셀의 부서 코드로 “본사 소속” 여부를 판단해야 함. 본사 인원 규모는 약 40명 미만으로 운영상 전제가 있음. |
| **Options** | A. 부서코드 `01`, `07`, `15`만 비본사(현장 등), 그 외 전부 본사 / B. 코드 매핑표(부서코드→본사/현장)를 별도 마스터로 관리 / C. 인사 시스템 연동 필드로 본사 여부를 직접 수신 |
| **Decision** | **A** — 비교는 **엑셀에 저장된 부서코드 문자열과 정확히 일치**할 때만 `01`, `07`, `15`를 비본사로 본다. (예: `019`는 `01`과 동일하지 않으므로 **본사**로 분류.) |
| **Reason** | 오너가 제시한 규칙을 그대로 반영하고, 선행 0이 있는 코드(`019` 등)와 한 자리 코드(`01`)를 혼동하지 않기 위함. |
| **Impact Scope** | 근로자/직원 import·diff·표시 로직에서 `Employment.department_code`(또는 동일 의미 필드)를 해석하는 모든 후속 구현; 본사 인원 수 검증(40명 미만)은 데이터 정합성 점검·리포트에 활용 가능 |

---

### [DECISION-020]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-26 |
| **Title** | 인사 부서코드(엑셀 범례) 기반 권한·열람 범위 (MVP) |
| **Context** | 직원 엑셀 하단에 부서코드·부서명 범례가 명시되어 있으며, 동일 코드가 행 데이터의 부서코드와 대응한다(예: 황순철 → `19` 예산견적팀). 본 시스템의 **주관부서는 안전보건실**이며, MVP에서는 안전보건만 “메인 관리자” 축으로 둔다. |
| **Decision — 주관·메인 관리** | **안전보건실(코드 `04`)**이 시스템의 메인 관리자로 간주한다. **MVP 시점**에는 메인 관리자 구조를 **안전보건만**으로 둔다. |
| **Decision — 경영 최상위 열람** | **김홍수(대표이사)**, **이광훈(부사장)**은 **전 범위 열람·접근**이 가능하다(부서코드와 무관한 예외 주체로 둔다). |
| **Decision — 공사관리 팀** | **`05`~`10`**: 공사관리 1~5팀 — 각 **현장이 보유한 팀 이름**과 매칭한다. **`21`**: 공사관리팀 — **모든 현장**에 대한 관리팀으로, 1~5팀 범위를 포괄한다. |
| **Decision — 관급공사** | **`15`**(관급공사)는 **자신이 속한 해당 현장만** 열람할 수 있다. |
| **Decision — 그 외 부서** | 위에 해당하지 않는 부서는 **일반(열람 위주)**으로 두며, **관급공사(`15`)만** “해당 현장 한정” 열람 구조와 같이 **현장 단일 스코프**를 갖는다(그 외는 일반 열람). |
| **Decision — 코드 예시(범례와 정합)** | 엑셀 범례에 따른 부서명 매핑을 진실의 원천으로 삼는다(예: `01` 현장, `04` 안전보건실, `19` 예산견적팀 등). 구현 시 **코드 문자열은 엑셀에 저장된 값과 동일하게** 비교한다(앞자리만 잘라 `01`과 `019`를 동일시하지 않음 — DECISION-019와 동일 원칙). |
| **Reason** | 운영 주체(안전보건실)와 현장·관급·경영 예외를 분리해 권한 모델을 단순화하고, MVP 범위를 명확히 하기 위함. |
| **Impact Scope** | 향후 `Role`/`UIType` 확장, `department_code` 기반 서버 권한, 현장 스코프 필터, HQ 사용자 목록·대시보드 API; 대표/부사장 예외는 계정 단위 플래그 또는 별도 화이트리스트로 구현 시 결정 |

---

### [DECISION-021]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 삼성 파일럿·데모 기준 현장을 화성 기아(SITE001)에서 청라 C18BL(SITE002)로 전환 |
| **Context** | 화성 기아 현장은 취소되었고, 파일럿(삼성 인정제 오버라이드·미연결 SITE 기본 현장·데모 시드 우선순위)을 C18 현장으로 옮긴다. |
| **Options** | A. 파일럿만 코드상 SITE002로 전환 / B. 시드 데모 계정·샘플 데이터·목록 정렬까지 C18 우선으로 정합 |
| **Decision** | **B** — `SITE002`를 파일럿으로 고정하고, 시드의 `site01`·`worker01`·일일작업계획·반려 샘플을 C18에 두며 목록 정렬에서 C18을 앞세운다. |
| **Reason** | 운영·데모에서 “파일럿=C18”이 일관되게 보이도록 하기 위함. |
| **Impact Scope** | `documents/service.py` 파일럿 코드, `document_settings/routes.py` `_PILOT_SITE_CODE`, `auth/routes.py` 미연결 SITE 기본 현장, `sites/ordering.py`, `seed/seed_data.py`, `HQDocumentsDashboardPage.vue`의 `(삼성인정제)` 표시 키워드 |
| **Supersedes context in** | [DECISION-011], [DECISION-016] 문맥 중 “화성기아현장만 파일럿” 표현은 본 결정으로 **청라 C18BL(SITE002)** 로 대체된다(런타임 `pilot` 교체 설계 원칙은 동일). |

---

### [DECISION-022]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 공개 데모: 문서취합은 파일럿 현장만, 홈 모니터링은 클릭 시 전체 현장 노출 |
| **Context** | 홈페이지·GitHub 공개 배포 시 타 현장 데이터 노출을 줄이면서, 본사 홈에서는 필요 시 나머지 현장 카드를 펼쳐 볼 수 있어야 함. |
| **Options** | A. 문서취합만 프론트 필터 / B. API `site_code` 파라미터 + Vite `VITE_DEMO_PILOT_SITE_CODE`로 문서취합·미결재·홈 대시보드 요약을 일관 제한, 홈 카드 목록은 토글로 전체 표시 |
| **Decision** | **B** |
| **Reason** | 응답 payload를 줄이고, 홈에서 “다른 현장 보기”로 전체 카드·요약을 다시 불러오도록 분리한다. |
| **Impact Scope** | `GET /documents/hq-dashboard`, `GET /documents/hq-pending`의 `site_code` 쿼리, `HQDocumentsDashboardPage.vue`, `HQSafeDashboard.vue`, `HQPendingDocumentsPage.vue`, `frontend/.env.example` |

---

### [DECISION-023]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | HQ_SAFE에 UI 전용 `문서 탐색` 화면을 신규 추가 |
| **Context** | 스티치 시안을 기준으로 현장 문서, 양식, 기준자료를 한곳에서 보는 탐색형 화면이 필요하나, MVP 범위에서는 API 연동 없이 더미 데이터와 상태 전환만 제공한다. |
| **Options** | A. 기존 문서취합 화면 안에 섹션 추가 / B. HQ_SAFE child route로 `/hq-safe/document-explorer` 신규 페이지 추가 |
| **Decision** | **B** |
| **Reason** | 기존 문서취합 운영 화면과 탐색형 화면의 목적이 달라 혼합 시 복잡도가 커지므로, 구조는 기존 HQ_SAFE 셸을 유지한 채 별도 child route로 분리한다. |
| **Impact Scope** | `frontend/src/pages/hq/HQDocumentExplorerPage.vue`, `frontend/src/router/index.ts`, `frontend/src/layouts/HQSafeLayout.vue` |

---

### [DECISION-024]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 공개 시연 기본 상태는 파일럿 포함 전 현장 문서 0건·제출률 0%로 시작 |
| **Context** | 시연에서는 문서를 실제로 업로드한 뒤 퍼센트가 올라가야 하므로, 시드 단계에서 반려 샘플이나 기존 업로드가 남아 있으면 안 된다. 또한 홈 대시보드 현장 카드 퍼센트는 가중치 점수가 아니라 실제 제출률을 보여야 한다. |
| **Options** | A. 기존 샘플 문서 유지 / B. 시드 실행 시 문서 관련 데이터를 비우고, 홈 대시보드 퍼센트는 `submission_rate`를 그대로 표시 |
| **Decision** | **B** |
| **Reason** | “업로드 전 0%, 업로드 후 상승”이라는 시연 흐름을 데이터와 UI 모두에서 일치시켜야 하기 때문이다. |
| **Impact Scope** | `frontend/src/pages/dashboard/HQSafeDashboard.vue`, `frontend/src/config/demoPilotSite.ts`, `backend/app/seed/seed_data.py`, 로컬 SQLite/`storage/documents` 초기 상태 |

---

### [DECISION-025]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 문서 탐색 1차 MVP는 실파일 스캔 + 파일명/상대경로 문자열 검색만 사용 |
| **Context** | 이번 단계의 목표는 실제 저장 파일이 화면에 정확히 보이도록 하는 것이며, 검색 품질 개선이나 인덱싱 구조는 범위에서 제외한다. |
| **Decision — 금지** | PostgreSQL FTS, `tsvector`, GIN, 파일 본문 인덱싱, PDF/DOCX/HWP 내용 파싱, 별도 인덱싱 DB, 백그라운드 인덱서 구현은 이번 범위에서 모두 금지한다. |
| **Decision — 검색 범위** | 검색은 **파일명(`name`)** 과 **상대경로(`relative_path`)** 에 대한 단순 `includes()` 매칭만 허용한다. 문서 본문·키워드 의미 검색은 하지 않는다. |
| **Decision — API** | 우선 `GET /document-explorer/list`, `GET /document-explorer/search` 두 개만 사용한다. |
| **Reason** | 인덱싱 없이도 실제 파일 노출과 기본 탐색 시연은 가능하며, 이번 MVP의 목표와 구현 범위를 명확히 제한하기 위함이다. |
| **Impact Scope** | `backend/app/modules/document_explorer/routes.py`, `backend/app/schemas/document_explorer.py`, `frontend/src/pages/hq/HQDocumentExplorerPage.vue` |

---

### [DECISION-026]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 문서 탐색 1차 MVP의 실파일 기준 폴더는 `docs/base` |
| **Context** | 사용자가 실제 시연용 파일을 `D:\\besma-rev\\docs\\base` 아래에 넣어 관리하고 있으며, 문서 탐색은 이 경로의 파일이 화면에 보여야 한다. |
| **Decision** | 문서 탐색의 base 폴더는 `storage/documents`가 아니라 **`docs/base`** 로 고정한다. |
| **Reason** | 사용자가 직접 준비한 시연 파일 위치와 탐색 대상 경로를 일치시켜야 즉시 검증 가능하기 때문이다. |
| **Impact Scope** | `backend/app/config/settings.py`의 `document_explorer_base_dir`, `backend/app/modules/document_explorer/routes.py`, 관련 테스트 |

---

### [DECISION-027]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 문서 탐색 1차 법령 연동은 파일 결과 아래 병렬 섹션으로 추가 |
| **Context** | `HQDocumentExplorerPage.vue`에서 같은 검색어로 파일 탐색 결과와 관련 법령 결과를 함께 보여주되, 기존 파일 탐색 사용성을 깨지 않아야 한다. |
| **Options** | A. 파일 결과 아래에 `관련 법령` 섹션 추가, 검색어가 있을 때만 법령 API 병렬 호출 / B. 2열 고정 패널로 기본 법령 목록까지 표시 / C. 파일/법령 탭 분리 |
| **Decision** | **A** |
| **Reason** | 기존 파일 결과 영역을 그대로 유지하면서 같은 검색어 기반 병렬 조회를 가장 작은 변경으로 만족시키고, 검색어가 없을 때 법령 목록이 본래 탐색 흐름을 흐리지 않게 하기 위함이다. |
| **Impact Scope** | `frontend/src/pages/hq/HQDocumentExplorerPage.vue`, 신규 법령 검색 API, 관련 테스트 |

---

### [DECISION-028]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 문서 탐색은 SITE에도 동일 기능으로 노출 |
| **Context** | 문서 탐색은 현재 `HQ_SAFE` 전용 route/menu에만 연결되어 있으나, 현장 사용자가 타 현장 자료를 벤치마킹하고 기준자료/법령을 더 자주 탐색해야 한다는 요구가 확정되었다. |
| **Options** | A. `SITE`에도 별도 child route(`/site/document-explorer`)와 메뉴를 추가하고 기존 화면 컴포넌트를 재사용 / B. 권한만 열고 메뉴는 미노출 / C. SITE에서 HQ route로 이동 |
| **Decision** | **A** |
| **Reason** | 현장 사용자가 메뉴에서 자연스럽게 접근할 수 있어야 하며, 같은 탐색 기능을 기존 컴포넌트 재사용으로 가장 작게 확장할 수 있기 때문이다. 추후 AI 탐색 연동 전 단계의 인덱스/문자열 탐색 기능도 현장에 우선 가치가 있다. |
| **Impact Scope** | `frontend/src/router/index.ts`, `frontend/src/layouts/SiteLayout.vue`, 기존 `frontend/src/pages/hq/HQDocumentExplorerPage.vue` 재사용 |

---

### [DECISION-029]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | `소통자료`는 DECISION-002 예외로 신규 `communications` 모듈 허용 |
| **Context** | SITE 사용자 전용 사진 공유 MVP(업로드/수신함/읽음처리/미확인 배지)는 문서/TBM 흐름과 분리된 독립 기능이 필요하다. 사용자 승인으로 본 건은 DECISION-002의 예외로 처리한다. |
| **Options** | A. 신규 `app/modules/communications` + `/communications/*` + 신규 테이블 3종 / B. 기존 문서 모듈에 편입 / C. 알림 등 다른 모듈에 편입 |
| **Decision** | **A (예외 승인)** |
| **Reason** | 문서/TBM과의 교차영향 없이 격리된 MVP를 가장 작게 구현하면서 요구된 API/UX를 그대로 만족한다. |
| **Impact Scope** | `backend/app/modules/communications/*`, Alembic 신규 migration, SITE 전용 프론트 라우트/메뉴/페이지 |

---

### [DECISION-030]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 지도 기반 현장검색은 `/site/info` 실구현 + HQ 전용 검색 라우트 추가로 진행 |
| **Context** | 기존 `SiteLayout`의 `/site/info`는 placeholder 링크였고, 요구사항은 주소 지도 연동 + 지도앱 선택 + HQ도 현장검색 접근을 포함한다. |
| **Options** | A. placeholder 유지 / B. 준비중 페이지 / C. `/site/info`를 실제 설정/현장정보 화면으로 구현 + `map_preference` 저장. HQ 접근은 별도 HQ 라우트 추가(OPEN-024: B). |
| **Decision** | **C + B** |
| **Reason** | 지도 기능 요구를 충족하면서 `meta.uiType` 분리 원칙을 유지하고, 기존 문서/TBM 흐름과 교차영향 없이 최소 확장으로 배포 가능하다. |
| **Impact Scope** | `backend/app/modules/users/*`, `backend/app/modules/sites/*`, `frontend/src/router/index.ts`, `SiteLayout/HQSafeLayout` 메뉴 및 신규 SITE/HQ 검색·정보 페이지 |

---

### [DECISION-031]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-30 |
| **Title** | 중복 현장 중 주소 없는 항목은 검색에서 숨기고, C18 기본 연결은 주소 있는 항목으로 고정 |
| **Context** | `청라C18`/`화성 기아`가 중복 존재하며, 주소 없는 항목까지 검색/기본 연결에 노출되어 지도 연결과 업로드 현장 식별에 혼선이 발생했다. |
| **Options** | A. 중복 모두 노출 유지 / B. 주소 없는 항목 숨김 + 기본 연결은 주소 있는 C18 우선 / C. 즉시 DB 물리 정리(삭제/병합) |
| **Decision** | **B** |
| **Reason** | 즉시 배포 안정성을 유지하면서 사용자 혼선을 제거하고, 업로드/지도 기준 현장을 주소 있는 항목으로 일관화할 수 있다. |
| **Impact Scope** | `GET /sites/search`, SITE 로그인 기본 site 보정, 시드/데모 사용자 site 매핑, HQ 기본 노출 정렬 |

---

### [DECISION-032]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-03-31 |
| **Title** | 비밀번호 변경 시 복잡도 규칙 폐지·데모 공통 초기 비밀번호 `temp@12` |
| **Context** | [OPEN-025]에서 B안 확정. 파일럿·데모에서 사용자가 임의 비밀번호로 바꿀 수 있어야 하며 최소 길이·특수문자 등 복잡도는 요구하지 않는다. 데모 계정(`hq01`~`hq05`, `site01`~`site03`) 시드 기본 비밀번호는 이전 `Temp@1234`에서 짧은 공통값으로 통일한다. |
| **Options** | A. 복잡도 유지 / B. 복잡도 제거(공백 불가만) + 데모 기본 `temp@12` / C. 복잡도 제거 + 설정 화면 링크 추가 |
| **Decision** | **B** |
| **Reason** | 운영·시연 편의와 오너 선택에 따름. [DECISION-018] 최초 로그인 강제 변경(`must_change_password`) 및 서버 403 차단 플로우는 **유지**한다. |
| **Impact Scope** | `backend/app/modules/auth/routes.py`(`_validate_new_password`), `frontend/src/pages/auth/ChangePasswordPage.vue`, `demo_login_users.py`, `scripts/create_demo_login_users.py`, 관련 테스트 |

---

### [DECISION-033]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-01 |
| **Title** | 서비스 노출 명칭은 `BESMA 임시플랫폼`, HQ_SAFE 기본 진입은 문서 탐색 |
| **Context** | 운영 전환 후 `Local` 표기가 사용자 인지와 맞지 않으며, HQ_SAFE 로그인 직후 기본 진입 화면을 기존 TBM 모니터가 아닌 문서 탐색으로 바꾸고자 한다. 또한 미완료 메뉴임을 명확히 하기 위해 특정 메뉴에 `(공사중)` 표기를 추가한다. |
| **Options** | A. 명칭 일괄 전환 + 기본 진입 `문서 탐색` + 메뉴 `(공사중)` 표기 / B. 명칭만 전환 / C. 기본 진입만 전환 |
| **Decision** | **A** |
| **Reason** | 운영 상태에 맞는 브랜드/카피 일관성을 확보하고, 사용자가 요구한 첫 화면 흐름과 미구현 메뉴 인지성을 동시에 최소 변경으로 반영하기 위함. |
| **Impact Scope** | `frontend/index.html`, `frontend/src/router/index.ts`, `frontend/src/pages/LoginPage.vue`, `frontend/src/layouts/HQSafeLayout.vue`, 기타 `Local` 표기 화면 문자열 |

---

### [DECISION-034]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-01 |
| **Title** | 테스트 계정은 혼합 권한(B): HQ 읽기전용 + SITE 테스트현장 업로드 허용 |
| **Context** | 테스트 계정(`test1/test1@`, `site1/site1@`) 운영에서 다른 현장 노출을 막고, 테스트 업로드 후 HQ에서 확인/다운로드 가능한 시나리오가 필요하다. |
| **Options** | A. 두 계정 완전 읽기전용 / B. `test1` 읽기전용 + `site1` 테스트현장 업로드 허용 / C. 테스트 전용 role 신설 |
| **Decision** | **B** |
| **Reason** | 시연 요구(현장 업로드→본사 확인)를 충족하면서 권한 범위를 테스트 현장으로 제한해 회귀 위험을 낮출 수 있기 때문이다. |
| **Impact Scope** | 인증/권한 분기, 테스트 계정 시드, 테스트 전용 현장 스코프, 업로드 용량 제한(10MB), HQ/SITE 테스트 동선 |

---

### [DECISION-035]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-01 |
| **Title** | `운영 아이디어 제안`은 기존 `opinions`를 재사용해 서버 저장 |
| **Context** | 테스트버전/현재버전 모두에서 메뉴를 추가해 운영 아이디어를 수집하되, 별도 모듈 신설 없이 빠르게 운영하고자 한다. 사용자는 메뉴 클릭 시 이름/아이디어를 확인하고, 이름은 자유 입력을 원한다. |
| **Options** | A. 기존 `opinions` 재사용(메뉴/화면 카피 변경) / B. 신규 전용 모듈·테이블 / C. 메뉴만 추가 후 추후 구현 |
| **Decision** | **A** |
| **Reason** | 서버 저장과 조회 요구를 충족하면서 변경 범위를 최소화하고 기존 운영 흐름과 충돌을 줄일 수 있다. |
| **Impact Scope** | `frontend/src/layouts/*Layout.vue`, `frontend/src/pages/opinions/*`, `backend /opinions` API 재사용 경로 |

---

### [DECISION-036]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-02 |
| **Title** | 데모 활성 계정 범위(B): hq01~hq05 읽기전용, site01~site03만 업로드 허용 |
| **Context** | 운영/시연 혼선을 줄이기 위해 활성 로그인 계정을 hq01~hq05, site01~site03로 한정하고, 업로드는 현장 테스트 계정(site01~site03)만 수행할 수 있어야 한다. HQ 데모 계정은 읽기 전용이어야 한다. |
| **Options** | A. HQ/SITE 모두 업로드 허용 / B. HQ(hq01~hq05)는 업로드 차단 + SITE(site01~site03)만 업로드 허용 / C. HQ/SITE 업로드 모두 차단 |
| **Decision** | **B** |
| **Reason** | “현장 업로드 → 본사 검토” 시나리오를 유지하면서 HQ 데모 계정 업로드로 인한 데이터 혼선을 막기 위해서다. |
| **Impact Scope** | `backend/app/modules/document_submissions/routes.py` 업로드 권한 가드 |

---

### [DECISION-037]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-02 |
| **Title** | HQ에 “주기 기반 문서 모니터링” 레이어를 추가하고 TBM을 월간 집계형 운영데이터로 분리 표시 |
| **Context** | TBM은 일일 누적 데이터이며 일반 월간 문서처럼 HQ 문서취합 메인 매트릭스에 혼합하면 화면 과밀화 및 승인/반려 단위 왜곡이 발생한다. HQ 문서취합/문서탐색/로그인/배포 흐름은 유지하면서, TBM을 “주기 기반 모니터링”의 첫 대표 케이스로 구현해야 한다. |
| **Decision** | **TBM은 신규 “주기 기반 문서 모니터링” 화면에서 월간 집계 + 일별 drill-down으로 관리한다.** |
| **Options** | A. 기존 `HQDocumentsDashboardPage` 매트릭스에 TBM을 “월간 집계형”으로 억지 결합 / B. HQ 문서취합 메인과 분리된 “주기 기반 문서 모니터링” 신규 화면(이 레이어의 첫 케이스로 TBM 월간 집계/일별 drill-down 구현) |
| **Reason** | TBM만 예외 처리하는 임시방편이 아니라, 향후 주간/격주/월간/분기/연간 항목으로 확장 가능한 역할 분리 레이어를 확보하기 위해서다. |
| **Impact Scope** | 프론트: HQ 신규 라우트/화면 추가 + drill-down UI / 백엔드: TBM 월간 집계 및 일별 drill-down API 추가 + 테스트 추가 |

---

### [DECISION-038]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | 문서 탐색 검색 범위를 `docs/base` + `storage/documents`로 확장 |
| **Context** | 문서 탐색은 `docs/base`만 스캔하여 현장에서 업로드된 실제 제출 서류(`storage/documents`)가 검색되지 않았다. 사용자 요청으로 기준자료와 현장 제출본을 한 화면에서 함께 탐색해야 한다. |
| **Options** | A. `docs/base`만 유지 / B. `docs/base`와 `storage/documents`를 함께 검색 / C. `storage/documents`를 별도 동기화 후 `docs/base`만 검색 |
| **Decision** | **B** |
| **Reason** | 현장 업로드 문서가 즉시 탐색되어야 운영 흐름(업로드 -> 탐색/확인)에 맞고, 별도 동기화 작업 없이 가장 작은 변경으로 요구를 충족한다. |
| **Impact Scope** | `backend/app/modules/document_explorer/routes.py`, `backend/tests/test_document_explorer_routes.py`, 문서탐색의 현장문서 필터(`field`) 분류 규칙 |

---

### [DECISION-039]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | SITE 문서취합 화면은 전체 목록 단일 뷰 + 승인 하단 정렬로 전환 |
| **Context** | 현장 사용자가 법적 서류 안내문구와 상단 `오늘/이번주/이번달` 전환 없이 전체 문서를 한 번에 보고, 승인 완료 문서는 목록 하단으로 내려 우선 처리 대상을 먼저 보길 원했다. |
| **Options** | A. 요청안 그대로(단일 전체 목록, 안내문구/기간탭 제거, 승인 하단 정렬, 주기 한글 라벨) / B. 안내문구만 제거하고 기존 기간탭/작업큐 유지 / C. 현행 유지 |
| **Decision** | **A** |
| **Reason** | 현장 실행 흐름에서 “무엇을 지금 올릴지”를 빠르게 판단하려면 단일 전체 목록과 승인 하단 정렬이 가장 직관적이며, 기간 탭 전환 비용을 줄일 수 있다. |
| **Impact Scope** | `frontend/src/pages/site/SiteDocumentsDashboardPage.vue` (탭 제거, 단일 목록 정렬, 주기 라벨 한글화, 안내문구 제거) |
| **Supersedes** | [DECISION-009]의 “작업 큐 중심/기본 숨김” 표현 중 SITE 기본 화면 정책을 본 결정으로 대체한다. (상태 문자열 불변 원칙 [DECISION-005], [DECISION-010]은 유지) |

---

### [DECISION-040]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | SITE에 공지사항 게시판(댓글 포함)과 상단 티커를 추가 |
| **Context** | 현장 사용자가 대시보드 하위 메뉴에서 공지사항을 게시판 형태로 확인하고, 문서처럼 공지에 대해 댓글로 소통할 수 있어야 한다. 또한 최근 공지 2건 제목을 현장명 헤더 바로 아래에서 깜빡이는 띠로 항상 노출해야 한다. |
| **Options** | A. 최소 MVP(게시판+댓글+최근 2건 깜빡이는 티커) / B. 운영형 확장(고정공지/첨부/검색 포함) / C. 댓글 없는 공지 목록 |
| **Decision** | **A** |
| **Reason** | 요구 핵심(게시판형 + 댓글 + 상단 즉시 노출)을 가장 빠르게 충족하면서 기존 UI/권한 구조를 크게 흔들지 않는다. |
| **Impact Scope** | `backend/app/modules/notices/*`, `backend/app/main.py`, `backend/app/core/database.py`, `frontend/src/pages/site/SiteNoticeBoardPage.vue`, `frontend/src/layouts/SiteLayout.vue`, `frontend/src/router/index.ts` |

---

### [DECISION-041]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | 단일 메뉴 `안전보건 방침 및 목표`를 역할별로 분기해 노출 |
| **Context** | 공지사항 아래에 신규 메뉴를 두고, HQ는 본사 방침/목표를 업로드 및 2패널 동시 조회해야 하며, SITE는 기본적으로 현장 방침/목표를 보되 버튼으로 본사 방침/목표로 전환 조회해야 한다. |
| **Options** | A. 단일 메뉴 + 역할별 화면 분기 / B. 메뉴 2개 분리 / C. 탭 구조 고정 |
| **Decision** | **A** |
| **Reason** | 사용자 요청 흐름(HQ 업로드, SITE 기본 현장 표시, 본사 전환 버튼)을 가장 적은 구조 변경으로 일관되게 충족한다. |
| **Impact Scope** | `backend/app/modules/safety_policy_goals/*`, `backend/app/main.py`, `backend/app/core/database.py`, `frontend/src/pages/site/SafetyPolicyGoalsPage.vue`, `frontend/src/layouts/SiteLayout.vue`, `frontend/src/layouts/HQSafeLayout.vue`, `frontend/src/router/index.ts` |

---

### [DECISION-042]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | 모바일 운영에서 방침/목표 메뉴 제외, 문서탐색은 PDF 전용으로 제한 |
| **Context** | 모바일 사용자는 현장 실행 중심으로 `미업로드 문서 확인`, `현장 검색`, `위험성평가 DB 검색` 동선이 우선이며, 모바일에서 방침/목표 메뉴는 제외 요청이 확정되었다. 또한 문서탐색은 PDF 파일만 검색/열람하도록 단순화해야 한다. |
| **Options** | A. 모바일 실행 동선 우선 + PDF 전용 탐색 / B. 기존 메뉴·탐색 범위 유지 / C. 모바일/데스크톱 동일 유지 |
| **Decision** | **A** |
| **Reason** | 모바일 현장 사용성(즉시 실행)과 탐색 결과 일관성(PDF 문서만) 요구를 동시에 충족한다. |
| **Impact Scope** | `frontend/src/layouts/SiteLayout.vue`, `frontend/src/pages/site/SiteMobileOpsPage.vue`, `backend/app/modules/document_explorer/routes.py`, `frontend/src/pages/hq/HQDocumentExplorerPage.vue` |

---

### [DECISION-043]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | 안전 교육/안전 점검/부적합사항 메뉴를 추천값(A2+B1+C1+D2)으로 구현 |
| **Context** | 신규 메뉴 3종에 대해 교육자료 업로드/조회, 점검 파일 게시판+코멘트 소통, 부적합사항관리대장 엑셀 업로드 후 표시/다운로드/PDF 보기 및 개선조치(사진 리사이즈, 일자, 담당자) 편집 요구가 확정되었다. |
| **Decision — 분류 기준** | 교육자료는 **전용 업로드 버튼(A2)** 으로 등록한다. |
| **Decision — 점검 소스** | 안전 점검 게시판은 문서취합의 **`INSPECTION` 계열 전체(B1)** 를 업로드 순으로 노출한다. |
| **Decision — 대장 원본** | 부적합사항관리대장은 **엑셀(xlsx) 업로드 후 서버 파싱(C1)** 으로 표시한다. |
| **Decision — 편집 권한** | 개선조치(내용/일자/담당자)와 사진 업로드는 **SITE/HQ 모두 작성 가능(D2)** 으로 둔다. |
| **Reason** | 요청 기능을 최소 확장으로 빠르게 제공하면서 기존 문서 저장소/권한 구조를 재사용해 운영 전환 속도를 높인다. |
| **Impact Scope** | `backend/app/modules/safety_features/*`, `backend/app/main.py`, `backend/app/core/database.py`, `frontend/src/pages/site/SafetyEducationPage.vue`, `SafetyInspectionBoardPage.vue`, `NonconformityPage.vue`, `frontend/src/layouts/SiteLayout.vue`, `frontend/src/layouts/HQSafeLayout.vue`, `frontend/src/router/index.ts` |

---

### [DECISION-044]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | `근로자의견청취`는 3단계 워크플로우(현장승인 -> 본사확인 -> 포상후보)로 구현 |
| **Context** | 사용자 요청으로 `근로자 의견청취 관리대장` 업로드 기반 목록에서 상태 전이와 권한(현장/본사)을 명확히 분리해야 했다. |
| **Options** | A. 3단계 고정 워크플로우(현장승인 -> 본사확인 -> 포상후보) / B. 단일 상태 + 자유 코멘트 / C. 2단계(현장확인 -> 본사확인) |
| **Decision** | **A** |
| **Reason** | 사용자 행동 흐름과 권한 책임 구분을 가장 명확히 반영하며, 대장 기반 운영에서 후속 포상후보 선별까지 일관된 상태 전이가 가능하다. |
| **Impact Scope** | `backend/app/modules/safety_features/routes.py`, `backend/app/modules/safety_features/models.py`, `frontend/src/pages/site/WorkerVoiceBoardPage.vue`, `frontend/src/layouts/SiteLayout.vue`, `frontend/src/layouts/HQSafeLayout.vue`, `frontend/src/router/index.ts` |

---

### [DECISION-045]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | HQ 설정 기반 동적 메뉴(A) + 방침/목표 아래 정렬(DnD) + 저장 확정 |
| **Context** | 사용자는 기본 고정 메뉴는 유지하되 HQ 로그인 시 게시판형/표형 메뉴를 수시로 추가·변형·삭제하고, 메뉴 순서를 드래그앤드롭으로 조정한 뒤 저장 버튼으로 확정하길 원했다. |
| **Options** | A. 전역 동적 메뉴 레지스트리 + 타입별 공통 렌더러 / B. 메뉴별 코드 생성 / C. 하이브리드(JSON 공용 저장) |
| **Decision** | **A** |
| **Reason** | 운영 중 메뉴 증감/변형이 잦은 요구에 가장 유연하고, 방침/목표 아래 동적 정렬과 저장 확정 UX를 일관되게 제공할 수 있다. |
| **Impact Scope** | `backend/app/modules/document_settings/models.py`, `backend/app/modules/document_settings/routes.py`, `backend/alembic/versions/*dynamic_menus*.py`, `frontend/src/pages/hq/HQDocumentSettingsPage.vue`, `frontend/src/layouts/SiteLayout.vue`, `frontend/src/layouts/HQSafeLayout.vue`, `frontend/src/pages/site/DynamicMenuRuntimePage.vue`, `frontend/src/router/index.ts` |

---

### [DECISION-046]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | 현장 노출/지표는 C18BL 중심으로 축소하고 로그인 기본 진입을 문서취합/내현장문서로 고정 |
| **Context** | C18 현장이 중복 노출되어 운영 혼선이 발생했고, 대시보드/지표를 C18BL 기준으로 단순화하며 로그인 직후 기본 화면을 문서 실행 중심으로 통일할 필요가 있었다. |
| **Options** | A. C18 업로드 현장 1개 유지 + 기타 샘플 최소 노출 + 지표 C18 고정 + 기본진입 HQ 문서취합/SITE 내현장문서 / B. 현행 유지 |
| **Decision** | **A** |
| **Reason** | 시연·운영에서 노이즈를 줄이고 핵심 동선(문서취합/내현장문서)으로 즉시 진입하게 해 사용 혼선을 최소화한다. |
| **Impact Scope** | `backend/app/modules/sites/routes.py`, `backend/app/modules/auth/routes.py`, `backend/app/modules/dashboard/routes.py`, `frontend/src/config/demoPilotSite.ts`, `frontend/src/pages/dashboard/HQSafeDashboard.vue`, `frontend/src/router/index.ts` |

---

### [DECISION-047]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | 공지사항 메뉴를 HQ_SAFE에도 노출하고 SITE와 동일 게시판을 공유 |
| **Context** | 기존 구현은 SITE 전용 공지사항 메뉴/라우트만 있어 hq01(HQ_SAFE) 로그인 시 공지사항 접근이 불가능했다. 사용자 선택 `A`에 따라 HQ_SAFE에서도 동일 공지 게시판을 사용해야 한다. |
| **Options** | A. HQ_SAFE에 공지사항 메뉴 추가 + SITE와 동일 게시판 공유 / B. HQ_SAFE 읽기전용 / C. SITE 전용 유지 |
| **Decision** | **A** |
| **Reason** | 본사-현장 공지를 단일 게시판으로 운영하면 전달 경로가 단순해지고, HQ 로그인 사용자도 동일 공지 흐름을 즉시 확인할 수 있다. |
| **Impact Scope** | `frontend/src/layouts/HQSafeLayout.vue`, `frontend/src/router/index.ts` |

---

### [DECISION-048]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | 사이드바 메뉴는 대시보드 제외 전 항목을 순서 조정 가능하도록 통합 |
| **Context** | 사용자가 동적 메뉴만 따로 정렬하는 방식은 실제 운영 순서 조정에 불편하다고 판단하여, 고정 메뉴와 동적 메뉴를 함께 보고 순서를 맞추길 요청했다. 또한 대시보드는 최상단 고정으로 유지하길 명시했다. |
| **Options** | A. 동적 메뉴만 정렬 유지 / B. 대시보드 제외 전체 메뉴(고정+동적) 정렬 저장 / C. UI별 일부 메뉴만 정렬 허용 |
| **Decision** | **B** |
| **Reason** | 실제 사이드바 노출 순서와 설정 UI를 일치시켜 운영자가 직관적으로 메뉴 구조를 관리할 수 있다. |
| **Impact Scope** | `backend/app/modules/document_settings/models.py`, `backend/app/modules/document_settings/routes.py`, `backend/alembic/versions/20260410_0025_ui_menu_order_configs.py`, `frontend/src/pages/hq/HQDocumentSettingsPage.vue`, `frontend/src/layouts/SiteLayout.vue`, `frontend/src/layouts/HQSafeLayout.vue` |

---

### [DECISION-049]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-10 |
| **Title** | 사용설명서 화면 예시는 HQ 업로드 방식으로 운영하고, 방침/목표 404는 배포 미반영 안내를 표시 |
| **Context** | 사용설명서 스크린샷이 정적 파일 배치만 가능해 운영자가 즉시 반영하기 어려웠고, 운영 API 미반영 상태에서는 방침/목표 조회/업로드가 404로 실패해 원인 파악이 어려웠다. |
| **Options** | A. 정적 파일 수동 배치 유지 / B. HQ 업로드로 스크린샷 등록 + 404 배포 안내 문구 표시 / C. 전용 CMS 별도 구축 |
| **Decision** | **B** |
| **Reason** | 운영자가 화면에서 바로 이미지를 반영할 수 있어 유지보수성이 높고, API 미배포 상태를 사용자에게 명확히 알려 장애 대응 시간을 줄일 수 있다. |
| **Impact Scope** | `backend/app/modules/document_settings/routes.py`, `backend/app/main.py`, `frontend/src/pages/common/UserGuidePage.vue`, `frontend/src/pages/site/SafetyPolicyGoalsPage.vue` |

---

### [DECISION-050]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-12 |
| **Title** | `운영 아이디어 제안(opinions)` 삭제는 작성자 또는 관리자만 허용 |
| **Context** | 사용자가 제안 글을 삭제할 수 있어야 한다고 요청했고, 공지사항과 동일하게 권한 범위를 맞추길 원했다. |
| **Options** | A. 작성자 + `HQ_SAFE_ADMIN`/`SUPER_ADMIN` / B. 관리자만 / C. 소프트삭제 |
| **Decision** | **A** |
| **Reason** | 공지사항 삭제 정책과 일관되고, 작성자가 오등록 시 즉시 정정할 수 있다. |
| **Impact Scope** | `backend/app/modules/opinions/models.py`, `backend/app/modules/opinions/routes.py`, `backend/alembic/versions/20260412_0026_opinions_created_by_user_id.py`, `frontend/src/pages/opinions/OpinionListPage.vue`, `frontend/src/pages/opinions/OpinionDetailPage.vue` |

---

### [DECISION-051]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-12 |
| **Title** | 운영 아이디어 제안 상태는 한글 라벨(검토전·검토중·조치완료)로 표시하고 점수 UI는 사용하지 않는다 |
| **Context** | 운영 화면에서 영문 상태코드와 적절성/실행가능성 점수 입력이 불필요하다는 요청이 있었다. DB 상태 문자열은 유지하고 표시·필터 라벨만 한글로 통일한다. |
| **Options** | A. 표시·필터만 한글 + 점수 UI 제거 / B. 백엔드 상태값 자체를 한글 문자열로 변경 / C. 현행 유지 |
| **Decision** | **A** |
| **Reason** | API·기존 데이터와 호환을 유지하면서 화면만 단순화할 수 있다. |
| **Impact Scope** | `frontend/src/utils/opinionStatus.ts`, `frontend/src/pages/opinions/OpinionListPage.vue`, `frontend/src/pages/opinions/OpinionDetailPage.vue` |

---

### [DECISION-052]

| 항목 | 내용 |
|------|------|
| **Date** | 2026-04-12 |
| **Title** | 사용설명서 스크린샷 업로드·촬영팁은 `hq01` 전용, 업로드 이미지는 서버에서 자동 최적화 |
| **Context** | 현장·일반 본사 계정에는 촬영 안내가 불필요하고, 스크린샷 등록은 운영 편집 계정만 수행하길 원했다. 업로드 파일은 용량·표시 일관을 위해 자동 리사이즈·JPEG 변환이 필요하다. |
| **Options** | A. `hq01`만 업로드/촬영팁 노출 + 서버 JPEG 최적화 / B. `HQ_SAFE_ADMIN` 전체 / C. 프론트만 숨김 |
| **Decision** | **A** |
| **Reason** | 요청대로 편집 책임을 단일 계정으로 고정하고, 백엔드에서도 업로드를 막아 위변조·혼선을 줄인다. |
| **Impact Scope** | `frontend/src/pages/common/UserGuidePage.vue`, `backend/app/modules/document_settings/routes.py` |

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-03-20 | 초안 작성 — Decision 001~007 등록 |
| 2026-03-20 | Decision 008~010 추가 — HQ/SITE 문서 화면 운영 규칙 및 REJECTED UI 불변 규칙 |
| 2026-03-26 | Decision 019 추가 — 부서코드 기준 본사/비본사 구분 |
| 2026-03-26 | Decision 020 추가 — 부서코드 기반 권한·열람 범위(MVP) |
| 2026-03-30 | Decision 021 추가 — 파일럿 현장 C18(SITE002) 전환 |
| 2026-03-30 | Decision 022 추가 — 공개 데모 문서취합·홈 모니터링 노출 범위 |
| 2026-03-30 | Decision 023 추가 — HQ_SAFE 문서 탐색 신규 UI 라우트 |
| 2026-03-30 | Decision 024 추가 — 공개 시연 기본 문서 0건/0% 시작 |
| 2026-03-30 | Decision 025 추가 — 문서 탐색 1차 MVP 검색/인덱싱 범위 제한 |
| 2026-03-30 | Decision 026 추가 — 문서 탐색 base 폴더 `docs/base` 고정 |
| 2026-03-30 | Decision 027 추가 — 문서 탐색의 법령 결과는 파일 결과 아래 병렬 섹션으로만 추가 |
| 2026-03-30 | Decision 028 추가 — 문서 탐색을 SITE 메뉴/라우트에도 동일 기능으로 노출 |
| 2026-03-30 | Decision 029 추가 — 소통자료 신규 모듈을 DECISION-002 예외로 승인 |
| 2026-03-30 | Decision 030 추가 — 지도 기반 현장검색(placeholder 해소 + HQ 접근 라우트) 확정 |
| 2026-03-30 | Decision 031 추가 — 주소 없는 중복현장 숨김 및 주소 있는 C18 기본 연결 확정 |
| 2026-03-31 | Decision 032 추가 — 비밀번호 변경 복잡도 규칙 폐지·데모 기본 비밀번호 `temp@12` |
| 2026-04-10 | Decision 038 추가 — 문서 탐색 범위를 `docs/base` + `storage/documents`로 확장 |
| 2026-04-10 | Decision 039 추가 — SITE 문서취합을 단일 전체 목록 + 승인 하단 정렬로 전환 |
| 2026-04-10 | Decision 040 추가 — SITE 공지사항 게시판+댓글 및 상단 티커 추가 |
| 2026-04-10 | Decision 041 추가 — 안전보건 방침/목표 단일 메뉴 역할별 분기(HQ 업로드, SITE 현장기본+본사전환) |
| 2026-04-10 | Decision 042 추가 — 모바일 동선 우선(방침/목표 제외) 및 문서탐색 PDF 전용 제한 |
| 2026-04-10 | Decision 043 추가 — 안전 교육/점검/부적합사항 메뉴를 추천값(A2+B1+C1+D2)으로 구현 |
| 2026-04-10 | Decision 044 추가 — 근로자의견청취 3단계 워크플로우(A) 확정 |
| 2026-04-10 | Decision 045 추가 — HQ 설정 기반 동적 메뉴(A), 방침/목표 아래 DnD 정렬 후 저장 확정 |
| 2026-04-10 | Decision 046 추가 — C18BL 중심 노출/지표 고정 및 로그인 기본 진입(문서취합/내현장문서) 확정 |
| 2026-04-10 | Decision 047 추가 — 공지사항을 HQ_SAFE에도 노출하고 SITE와 동일 게시판을 공유 |
| 2026-04-10 | Decision 048 추가 — 대시보드 제외 전체 메뉴(고정+동적) 순서 조정/저장 지원 |
| 2026-04-10 | Decision 049 추가 — 사용설명서 이미지 HQ 업로드 및 방침/목표 404 배포 안내 표시 |
| 2026-04-12 | Decision 050 추가 — 운영 아이디어 제안 삭제 권한(작성자+관리자) |
| 2026-04-12 | Decision 051 추가 — 운영 아이디어 상태 한글 표시 및 점수 UI 제거 |
| 2026-04-12 | Decision 052 추가 — 사용설명서 스크린샷 hq01 전용 및 서버 이미지 최적화 |
