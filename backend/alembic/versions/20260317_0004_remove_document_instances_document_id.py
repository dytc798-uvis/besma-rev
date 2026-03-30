"""remove DocumentInstance.document_id to enforce single FK direction

Revision ID: 20260317_0004
Revises: 20260317_0003
Create Date: 2026-03-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260317_0004"
down_revision = "20260317_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "document_instances" not in tables:
        return

    cols = {c["name"] for c in insp.get_columns("document_instances")}
    if "document_id" not in cols:
        return

    index_names = {i.get("name") for i in insp.get_indexes("document_instances")}

    # SQLite: batch recreate to safely drop FK + column
    with op.batch_alter_table("document_instances", recreate="always") as batch:
        # document_id 컬럼에 대한 자동 인덱스가 존재할 수 있으므로 먼저 제거
        if "ix_document_instances_document_id" in index_names:
            batch.drop_index("ix_document_instances_document_id")
        batch.drop_column("document_id")


def downgrade() -> None:
    pass

