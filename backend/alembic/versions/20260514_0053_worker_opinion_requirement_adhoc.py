"""AUTO_WORKER_OPINION_LOG: ROLLING -> ADHOC (문서 취합 수시 그룹 정렬용)

Revision ID: 20260514_0053
Revises: 20260514_0052
Create Date: 2026-05-14

전용 메뉴는 제거되고 문서 취합에서만 다루므로, 시드와 동일하게 ``frequency='ADHOC'`` 로 맞춘다.
삭제·파일 스토리지 변경 없음.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260514_0053"
down_revision = "20260514_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        text(
            """
            UPDATE document_requirements
            SET frequency = 'ADHOC',
                due_rule_text = '수시 (필요 시)'
            WHERE code = 'AUTO_WORKER_OPINION_LOG'
              AND UPPER(COALESCE(frequency, '')) = 'ROLLING'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        text(
            """
            UPDATE document_requirements
            SET frequency = 'ROLLING',
                due_rule_text = '의견 등록 시 갱신'
            WHERE code = 'AUTO_WORKER_OPINION_LOG'
              AND UPPER(COALESCE(frequency, '')) = 'ADHOC'
              AND COALESCE(due_rule_text, '') = '수시 (필요 시)'
            """
        )
    )
