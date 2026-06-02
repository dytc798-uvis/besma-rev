"""functional eval worker assigned evaluator login

Revision ID: 20260602_0059
Revises: 20260529_0058
Create Date: 2026-06-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260602_0059"
down_revision = "20260529_0058"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_index(inspector, table: str, index_name: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "functional_eval_workers" in inspector.get_table_names():
        if not _has_column(inspector, "functional_eval_workers", "assigned_evaluator_login_id"):
            with op.batch_alter_table("functional_eval_workers") as batch_op:
                batch_op.add_column(sa.Column("assigned_evaluator_login_id", sa.String(length=50), nullable=True))

        inspector = sa.inspect(bind)
        if not _has_index(inspector, "functional_eval_workers", "ix_functional_eval_workers_assigned_evaluator_login_id"):
            with op.batch_alter_table("functional_eval_workers") as batch_op:
                batch_op.create_index(
                    "ix_functional_eval_workers_assigned_evaluator_login_id",
                    ["assigned_evaluator_login_id"],
                    unique=False,
                )

        op.execute(
            sa.text(
                """
                UPDATE functional_eval_workers
                   SET assigned_evaluator_login_id = site_code
                 WHERE assigned_evaluator_login_id IS NULL
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "functional_eval_workers" in inspector.get_table_names():
        if _has_index(inspector, "functional_eval_workers", "ix_functional_eval_workers_assigned_evaluator_login_id"):
            with op.batch_alter_table("functional_eval_workers") as batch_op:
                batch_op.drop_index("ix_functional_eval_workers_assigned_evaluator_login_id")
        inspector = sa.inspect(bind)
        if _has_column(inspector, "functional_eval_workers", "assigned_evaluator_login_id"):
            with op.batch_alter_table("functional_eval_workers") as batch_op:
                batch_op.drop_column("assigned_evaluator_login_id")
