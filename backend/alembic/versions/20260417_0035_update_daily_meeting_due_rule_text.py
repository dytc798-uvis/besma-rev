"""update daily meeting due rule text

Revision ID: 20260417_0035
Revises: 20260416_0034
Create Date: 2026-04-17 13:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260417_0035"
down_revision = "20260416_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE document_requirements
            SET due_rule_text = :new_text
            WHERE code IN ('DAILY_RISK_ASSESSMENT', 'DAILY_SAFETY_MEETING_LOG')
            """
        ).bindparams(new_text="당일 안전회의 시 작성")
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE document_requirements
            SET due_rule_text = CASE
                WHEN code = 'DAILY_RISK_ASSESSMENT' THEN '당일 작업 시작 전 작성'
                WHEN code = 'DAILY_SAFETY_MEETING_LOG' THEN '당일 안전회의 후 작성'
                ELSE due_rule_text
            END
            WHERE code IN ('DAILY_RISK_ASSESSMENT', 'DAILY_SAFETY_MEETING_LOG')
            """
        )
    )
