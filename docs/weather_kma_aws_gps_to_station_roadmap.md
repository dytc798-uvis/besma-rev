# GPS → 가장 가까운 기상청 AWS 직접 관측값 전환 로드맵

**작성일**: 2026-08-07
**대상 시스템**: `D:\JSI\besma-rev\backend\app\modules\dashboard\weather_service.py`

## 현재 상태 (요약)
- 기상소스 라우팅은 추가됨: 기본 우선순위는 현재 `open-meteo`, `kma` 우선/폴백 전략 지원.
- KMA AWS 직접 관측(ASOS) 경로를 추가하고 GPS 기준 최근접 지점 선택 + 후보 목록 캐시를 적용.
- 기존 격자 기반 `getUltraSrtNcst`는 폴백 경로로 유지.
- 캐시 TTL 기준 재조회 처리 추가됨.

### 미완료/검증 보완 포인트
- `GPS → 가장 가까운 AWS 직접 관측값`의 실서비스 정합 검증 보강 필요.
- PTY/SKY 기반 라벨 매핑은 최소 매핑 적용 후 운영 검증 필요.
- 운영 환경에서의 API 키/권한/호출 실패 시 지표 수집은 추가 필요.
- 프런트에서 `temperature_source`를 노출/표시해 소스 투명성을 사용자에게 전달하지 않음.

## 최종 목표 정합 로드맵

### 1) AWS 정합 인프라 구축
- AWS 관측소 목록 소스 정리
  - [x] KMA ASOS 지점 API 기반 목록 캐시 획득(폴백 포함)
  - [ ] 항목: `station_id, station_name, lat, lon, nx, ny, active_from, active_to`
- 좌표→AWS 매핑 유틸리티
  - [x] `haversine` 거리 계산으로 최근접 AWS 선택
  - [x] 캐시 디스크 + TTL 7일 적용
  - [ ] 좌표가 같거나 변화량이 작을 경우 즉시 재사용

### 2) 기상청 관측 API 라우팅 확정
- 단계별 호출 순서
  - [x] 1순위: KMA AWS 직접 관측 (`ASOS` 기반)
  - [x] 실패/타임아웃 시 폴백: 기상청 격자 또는 open-meteo
- API 파라미터 정합
  - [ ] `base_time` 정합(발표 시각/갱신 주기 반영)
  - [ ] 응답 실패/빈값/지연 케이스에서 명시적 reason 리턴

### 3) 데이터 매핑/보정 안정화
- [ ] 온도/습도/풍속/강수/비상태 매핑 스키마 확정
  - `TA`(℃), `HM`(%), `WS`(m/s) 매핑 반영
  - 강수·구름 코드를 `PTY/SKY`로 변환하는 규칙 고도화
- [ ] 단위 미스매치 방지 검증
  - [ ] NaN/문자열/빈값 처리
  - [ ] 과거값 사용 금지(최신 타임스탬프 검증)

### 4) 캐시/표시/운영성
- [ ] 캐시 키에 `source + station_id + anchor + ttl` 반영
- [ ] 프런트에 `temperature_source`/`status_text` 표시
  - 사용자에게 오차 가능성/기상청 실패 시 소스 전환 알림
- [ ] 실패율/응답시간/폴백 횟수 로그 추가(운영 모니터링)

### 5) 검증 체크
- [ ] 현장 1곳에서 GPS(직위 좌표) 기준 과거/현재값 대조
- [ ] 온도 오차 2도/습도 오차 8%p 이슈 시나리오 재현 확인
- [ ] 배포 전 스테이징에서 스냅샷 갱신 테스트

## 실행 설정
- `BESMA_WEATHER_PRIMARY_SOURCE=kma`
- `BESMA_WEATHER_KMA_SERVICE_KEY=<기상청 인증키>`
- (선택) `BESMA_WEATHER_CACHE_TTL_MINUTES=20`
