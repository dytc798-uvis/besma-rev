# BESMA Session Start Required

> 이 문서는 새 세션이 시작될 때 가장 먼저 확인해야 하는 고정 진입 문서다.
> 작업자는 실제 구현 전에 아래 문서를 반드시 읽어야 한다.

## 필수 참조 문서

1. `docs/ai_collaboration_policy.md`
2. `docs/BESMA_SESSION_STATE.md`

## 필수 확인 사항

1. 현재 워크스페이스가 `D:\besma-rev`인지 확인한다.
2. `C:\BESMA`와 혼동하지 않았는지 확인한다.
3. 현재 프로젝트가 `FastAPI + Vue3 + SQLite` 로컬 MVP인지 확인한다.
4. `ai_collaboration_policy.md`에서 `Instruction Validation Gate`와 `Invariant Check` 규정을 읽는다.
5. `BESMA_SESSION_STATE.md`에서 현재 개발 단계, 열린 이슈, 다음 작업 계획을 읽는다.

## 작업 시작 규칙

1. 사용자 지시를 받으면 먼저 Instruction Validation Gate를 수행한다.
2. 구현 또는 설계 변경 후에는 반드시 Invariant Check를 수행한다.
3. 두 절차를 거치지 않으면 해당 작업은 완료로 간주하지 않는다.
