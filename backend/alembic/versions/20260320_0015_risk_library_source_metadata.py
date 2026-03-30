"""add risk library source metadata columns

Revision ID: 20260320_0015
Revises: 20260319_0014
Create Date: 2026-03-20

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260320_0015"
down_revision = "20260319_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("risk_library_item_revisions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("unit_work", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("process", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("source_file", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_sheet", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_row", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_page_or_section", sa.String(length=255), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE risk_library_item_revisions
               SET process = COALESCE(process, work_category)
             WHERE process IS NULL
            """
        )
    )

    with op.batch_alter_table("risk_library_item_revisions", schema=None) as batch_op:
        batch_op.alter_column("process", existing_type=sa.Text(), nullable=False)
        batch_op.create_index("ix_risk_library_item_revisions_unit_work", ["unit_work"], unique=False)
        batch_op.create_index("ix_risk_library_item_revisions_work_category", ["work_category"], unique=False)
        batch_op.create_index("ix_risk_library_item_revisions_trade_type", ["trade_type"], unique=False)
        batch_op.create_index("ix_risk_library_item_revisions_source_file", ["source_file"], unique=False)
        batch_op.create_index("ix_risk_library_item_revisions_source_row", ["source_row"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("risk_library_item_revisions", schema=None) as batch_op:
        batch_op.drop_index("ix_risk_library_item_revisions_source_row")
        batch_op.drop_index("ix_risk_library_item_revisions_source_file")
        batch_op.drop_index("ix_risk_library_item_revisions_trade_type")
        batch_op.drop_index("ix_risk_library_item_revisions_work_category")
        batch_op.drop_index("ix_risk_library_item_revisions_unit_work")
        batch_op.drop_column("source_page_or_section")
        batch_op.drop_column("source_row")
        batch_op.drop_column("source_sheet")
        batch_op.drop_column("source_file")
        batch_op.drop_column("note")
        batch_op.drop_column("process")
        batch_op.drop_column("unit_work")
