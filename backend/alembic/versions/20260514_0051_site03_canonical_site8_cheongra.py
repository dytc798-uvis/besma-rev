"""site03 → canonical site 8 + 2026-05-14 DAILY_TBM row move (청라 중복 SITE002 제거)

Revision ID: 20260514_0051
Revises: 20260514_0050
Create Date: 2026-05-14

운영 분석 요약 (EC2 SQLite, besma.db)
------------------------------------
- `sites.id=2` (SITE002): 문서 1건, 이력 1건 — 스텁 현장.
- `sites.id=8` (site_code 24025): 문서 112건, 이력 126건 — HQ dedupe 기준 청라 본류.
- `login_id='site03'` (user id 13)만 `site_id=8`으로 이동. 동일 현장 `site01`~`site05` 중
  나머지는 `site_id=2` 유지(광역 재매핑 금지).
- 당일 TBM: `documents.id=116`, `document_instances.id=116`, `document_upload_histories.id=130`,
  `period_start/end=2026-05-14`, `uploaded_by_user_id=13` → `site_id=8`으로만 이동.
- `sites` 테이블에 `is_active`/`merged_into_site_id` 컬럼 없음 → site 2 행 삭제/비활성 없음.

Canonical = **8** (HQ dedupe 및 문서·이력 부피 일치).

정책 (idempotent)
-----------------
1. `users`: `login_id='site03'` 이고 `site_id=2` 인 경우만 `site_id=8`.
2. `documents`: `site_id=2`, `document_type='DAILY_TBM'`, `period_start='2026-05-14'`,
   `uploaded_by_user_id` = site03의 `users.id` 인 행만 `site_id=8`.
3. `document_instances`: (2)에서 옮긴 문서의 `instance_id`에 해당하고 아직 `site_id=2`인
   인스턴스만 `site_id=8` (유니크 `(site_id, document_type_code, period_basis, period_start, period_end)`
   충돌 시 업그레이드는 실패하도록 그대로 둠 — 운영 DB에서 사전 확인됨).

Downgrade
---------
site03 사용자 및 위 조건의 문서/인스턴스를 `site_id=2`로 되돌린다(동일 조건 한정).
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260514_0051"
down_revision = "20260514_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    row = conn.execute(text("SELECT id FROM users WHERE login_id = :lid LIMIT 1"), {"lid": "site03"}).first()
    if row is None:
        return
    site03_id = int(row[0])

    conn.execute(
        text(
            """
            UPDATE users
            SET site_id = 8, updated_at = CURRENT_TIMESTAMP
            WHERE id = :uid AND login_id = 'site03' AND site_id = 2
            """
        ),
        {"uid": site03_id},
    )

    conn.execute(
        text(
            """
            UPDATE documents
            SET site_id = 8, updated_at = CURRENT_TIMESTAMP
            WHERE site_id = 2
              AND document_type = 'DAILY_TBM'
              AND period_start = '2026-05-14'
              AND uploaded_by_user_id = :uid
            """
        ),
        {"uid": site03_id},
    )

    conn.execute(
        text(
            """
            UPDATE document_instances
            SET site_id = 8
            WHERE site_id = 2
              AND id IN (
                SELECT instance_id FROM documents
                WHERE site_id = 8
                  AND document_type = 'DAILY_TBM'
                  AND period_start = '2026-05-14'
                  AND uploaded_by_user_id = :uid
                  AND instance_id IS NOT NULL
              )
            """
        ),
        {"uid": site03_id},
    )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(text("SELECT id FROM users WHERE login_id = :lid LIMIT 1"), {"lid": "site03"}).first()
    if row is None:
        return
    site03_id = int(row[0])

    conn.execute(
        text(
            """
            UPDATE document_instances
            SET site_id = 2
            WHERE site_id = 8
              AND document_type_code = 'DAILY_TBM'
              AND period_start = '2026-05-14'
              AND period_basis = 'AS_OF_FALLBACK'
              AND id IN (
                SELECT instance_id FROM documents
                WHERE site_id = 8
                  AND document_type = 'DAILY_TBM'
                  AND period_start = '2026-05-14'
                  AND uploaded_by_user_id = :uid
                  AND instance_id IS NOT NULL
              )
            """
        ),
        {"uid": site03_id},
    )

    conn.execute(
        text(
            """
            UPDATE documents
            SET site_id = 2, updated_at = CURRENT_TIMESTAMP
            WHERE site_id = 8
              AND document_type = 'DAILY_TBM'
              AND period_start = '2026-05-14'
              AND uploaded_by_user_id = :uid
            """
        ),
        {"uid": site03_id},
    )

    conn.execute(
        text(
            """
            UPDATE users
            SET site_id = 2, updated_at = CURRENT_TIMESTAMP
            WHERE id = :uid AND login_id = 'site03' AND site_id = 8
            """
        ),
        {"uid": site03_id},
    )
