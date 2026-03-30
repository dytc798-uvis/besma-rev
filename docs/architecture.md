# BESMA Local MVP 아키텍처 개요

## 백엔드

- FastAPI 기반 REST API
- 모듈별 디렉터리 구조
  - users, roles, sites, documents, approvals, opinions, dashboard, notifications
- 계층 분리 (향후 확장)
  - models (SQLAlchemy)
  - routes (FastAPI router)
  - service / repository (필요 시 추가)
- 인증
  - JWT 기반 토큰 발급
  - `role` / `ui_type` 기반 최소 권한 체크

## 데이터베이스

- SQLite (`database/besma.db`)
- ORM: SQLAlchemy
- 핵심 테이블:
  - users, sites, documents, approval_histories, opinions

## 프론트엔드

- Vue 3 + TypeScript + Vite
- Pinia 기반 상태 관리 (auth)
- Vue Router 기반 UI 타입 분기
  - `/hq-safe/**`, `/site/**`, `/hq-other/**`
- 레이아웃
  - `HQSafeLayout`, `SiteLayout`, `HQOtherLayout`

## 실행 흐름

1. 로그인
2. JWT 저장 후 `/auth/me` 로 사용자와 `ui_type` 조회
3. UI 타입에 따라 각각의 레이아웃/메뉴로 분기
4. 문서 / 의견 / 대시보드 등 모듈별 화면 접근

