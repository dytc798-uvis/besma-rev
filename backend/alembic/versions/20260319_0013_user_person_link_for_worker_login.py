"""add person_id link to users for worker login

Revision ID: 20260319_0013
Revises: 20260319_0012
Create Date: 2026-03-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260319_0013"
down_revision = "20260319_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}
    index_names = {idx["name"] for idx in inspector.get_indexes("users")}
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("users")}
    with op.batch_alter_table("users", schema=None) as batch_op:
        if "person_id" not in columns:
            batch_op.add_column(sa.Column("person_id", sa.Integer(), nullable=True))
        if "ix_users_person_id" not in index_names:
            batch_op.create_index("ix_users_person_id", ["person_id"], unique=False)
        if "fk_users_person_id_persons" not in foreign_keys:
            batch_op.create_foreign_key(
                "fk_users_person_id_persons",
                "persons",
                ["person_id"],
                ["id"],
            )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("fk_users_person_id_persons", type_="foreignkey")
        batch_op.drop_index("ix_users_person_id")
        batch_op.drop_column("person_id")
