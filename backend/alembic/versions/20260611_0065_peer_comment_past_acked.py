"""과거 문서 코멘트는 현장 확인 완료로 일괄 처리

Revision ID: 20260611_0065
Revises: 20260611_0064
Create Date: 2026-06-11
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision = "20260611_0065"
down_revision = "20260611_0064"
branch_labels = None
depends_on = None


def _kst_midnight_utc_naive() -> datetime:
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    kst_midnight = datetime.combine(today, datetime.min.time(), tzinfo=ZoneInfo("Asia/Seoul"))
    return kst_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def upgrade() -> None:
    cutoff = _kst_midnight_utc_naive().isoformat(sep=" ")
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO document_comment_site_acks (
                site_id, comment_id, acknowledged_by_user_id, ack_kind, acknowledged_at, created_at
            )
            SELECT
                d.site_id,
                c.id,
                COALESCE(
                    (SELECT u2.id FROM users u2
                     WHERE u2.site_id = d.site_id AND u2.role = 'SITE'
                     ORDER BY u2.id LIMIT 1),
                    1
                ),
                'legacy_past',
                :cutoff,
                :cutoff
            FROM document_comments c
            INNER JOIN documents d ON d.id = c.document_id
            INNER JOIN users u ON u.id = c.user_id
            WHERE c.created_at < :cutoff
              AND (
                u.role != 'SITE'
                OR u.site_id IS NULL
                OR u.site_id != d.site_id
              )
              AND NOT EXISTS (
                SELECT 1 FROM document_comment_site_acks a
                WHERE a.site_id = d.site_id AND a.comment_id = c.id
              )
            """
        ),
        {"cutoff": cutoff},
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM document_comment_site_acks WHERE ack_kind = 'legacy_past'"))
