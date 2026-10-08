# BESMA collection monitor 2026-10-08

운영 통합은 기존 NCP 아티팩트를 보존한 부분 패치다. 로컬의 기존 변경 전체를 운영에 배포하지 않는다.

- backend/app/modules/collection_monitor: 기존 인증을 사용하는 취합 현황/불변 NAS 사본/원본 export.
- frontend/public/collection-monitor.js, css: 기존 운영 Vue 번들 뒤에 추가. 기존 로그인 및 상세 검토 경로 유지.
- server_operations.py: 기존 운영 소스 해시 확인 및 부분 패치, besma 계정 DB 백업/추가, 운영 DB 사본 회귀검증. deploy 전 test 필요.
- sync_windows.py: 중앙 Windows PC 워커 재현 사본. 실제 실행 정본 D:\JSI\safety-workbench\tools\collection_monitor\sync.py. 기존 SSH 키는 E 경로에서만 읽으며 앱에 내장하지 않음.

대상 관급 코드: 24028,25037,25040,25059,25063,26004,26024,26052. 원래 21개 항목을 보존하고 부적합관리대장(주간), 근로자의견청취대장(월간)을 추가해 현장당23개.

NAS 정본: Z:\4. 안전보건관리실\★월간 자료 취합. 기존 7개 분류에서 기간/관급/현장별 버전 사본을 생성. 원본 삭제나 덮어쓰기 없음. 사본의 SHA-256 검증 뒤에만 서버 mirror receipt 저장.

네이버웍스 조회를 대체하지 않는다. 팀원이 NAS에 취합한 실제 파일만 서버에 보관한다. 공정표·서명지·사진대지·포상 선정평가는 취합률 분자에서 제외. 현장/기간을 확정할 수 없는 실제 문서는 확인 대상으로 남기고 관련 분류 취합률은 확인 필요로 표시한다. 수동 분류는 안전실 쓰기 역할만 가능하고 감사기록을 보존한다.

산출물 보관함은 개인 파일 보관 기능이며 본 취합 업무에 필수 아님. 메뉴만 숨기고 라우트/저장자료 보존.

배포 검증 상세: D:\JSI\workfiles\besma-collection-monitor-20261008\RESULT.md.
