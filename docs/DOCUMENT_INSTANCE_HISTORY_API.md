# DocumentInstance HQ 히스토리 API

## 목적

현장별 **주기 문서 인스턴스(`DocumentInstance`)** 기준으로 HQ가 업로드·검토 이력을 조회한다.  
행 단위 앵커는 `Document`가 아니라 `DocumentInstance`이며, `Document.instance_id`로 최대 1건의 `Document`를 연결한다.

## 파일·수정 범위

| 구분 | 경로 |
|------|------|
| 스키마 | `backend/app/schemas/document_instance_history.py` |
| 서비스 | `backend/app/modules/document_instances/service.py` |
| 라우트 | `backend/app/modules/document_instances/routes.py` |
| 앱 등록 | `backend/app/main.py` (`document_instances_router`) |
| 테스트 | `backend/tests/test_document_instance_history_api.py` |

**Impact scope:** 신규 read-only 엔드포인트만 추가. 기존 `/documents/*`, `/document-submissions/*` 계약 변경 없음.

## 인증·권한

- `Role.HQ_SAFE` 만 허용. 그 외 `403 Not allowed`.

## 엔드포인트

### `GET /document-instances/{instance_id}`

단일 `DocumentInstance` 스냅샷. `GET /document-instances/history` 목록의 각 `items[]` 원소와 **동일한 필드 계약**(`DocumentInstanceHistoryItem`).

- 존재하지 않으면 `404` (`detail: "Instance not found"`).
- 권한: `HQ_SAFE`만 (`403`).

직접 접근 예 (프론트 라우트는 배포 호스트에 맞게 조정):

- API: `GET https://<api-host>/document-instances/42`
- HQ 화면: `https://<app-host>/hq-safe/document-instances/42`

응답 예:

```json
{
  "instance_id": 42,
  "site_id": 10,
  "site_name": "청라 C18BL",
  "document_type_code": "DAILY_SAFETY_LOG",
  "document_name": "일일안전일지",
  "period_basis": "AS_OF_FALLBACK",
  "period_start": "2026-03-01",
  "period_end": "2026-03-01",
  "period_label": "2026-03-01 ~ 2026-03-01",
  "instance_status": "GENERATED",
  "workflow_status": "SUBMITTED",
  "is_missing": false,
  "document_id": 9001,
  "current_file_name": "일일안전일지_20260301.pdf",
  "uploaded_by_name": "김현장",
  "submitted_at": "2026-03-01T09:00:00",
  "reviewed_at": null,
  "review_note": null,
  "review_result": null,
  "submission_count": 1,
  "reupload_count": 0
}
```

### `GET /document-instances/history`

쿼리 파라미터 (모두 선택):

| 파라미터 | 설명 |
|----------|------|
| `site_id` | 현장 PK |
| `site_code` | 현장 코드 (`sites.site_code`) |
| `from_date` | `period_start >= from_date` |
| `to_date` | `period_start <= to_date` |
| `document_type_code` | 문서 유형 코드 |
| `limit` | 기본 200, 최대 2000 |
| `offset` | 페이지 오프셋 |

응답:

```json
{
  "items": [
    {
      "instance_id": 1,
      "site_id": 10,
      "site_name": "청라 C18BL",
      "document_type_code": "DAILY_SAFETY_LOG",
      "document_name": "일일안전일지",
      "period_basis": "AS_OF_FALLBACK",
      "period_start": "2026-03-01",
      "period_end": "2026-03-01",
      "period_label": "2026-03-01 ~ 2026-03-01",
      "instance_status": "GENERATED",
      "workflow_status": "NOT_SUBMITTED",
      "is_missing": true,
      "document_id": null,
      "current_file_name": null,
      "submitted_at": null,
      "reviewed_at": null,
      "review_note": null,
      "review_result": null,
      "submission_count": 0,
      "reupload_count": 0,
      "uploaded_by_name": null
    }
  ],
  "total": 1
}
```

### `GET /document-instances/history/summary`

동일 필터(`site_id`, `site_code`, `from_date`, `to_date`, `document_type_code`).

응답:

```json
{
  "total_instances": 100,
  "approved_count": 40,
  "under_review_count": 5,
  "rejected_count": 3,
  "missing_count": 12,
  "completion_rate": 40.0
}
```

- `completion_rate`: `approved_count / total_instances * 100` (인스턴스 0이면 `0`).
- `workflow_status` (응답 행 및 집계): `Document`가 없으면 `NOT_SUBMITTED`.
- `is_missing`: `period_end`가 **오늘(서버 로컬 날짜)** 보다 이전이고, 제출이 없으면 `true` (`Document` 없음 또는 `submitted_at` 없음).
- `submission_count`: 해당 `document_id`의 `document_upload_histories` 행 수.
- `reupload_count`: `max(submission_count - 1, 0)`.

## curl 예시

로컬 백엔드(`8001`) + HQ JWT를 `$TOKEN`에 둔 경우:

```bash
# 목록 (현장 ID)
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8001/document-instances/history?site_id=1&limit=50"

# 목록 (기간 + 유형)
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8001/document-instances/history?site_code=SITE002&from_date=2026-03-01&to_date=2026-03-31&document_type_code=DAILY_SAFETY_LOG"

# 요약
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8001/document-instances/history/summary?site_id=1"
```

토큰 발급 예:

```bash
curl -sS -X POST "http://127.0.0.1:8001/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=hq01&password=temp@12"
```

## 테스트

```bash
cd backend
python -m pytest tests/test_document_instance_history_api.py -q
```
