"""add dashboard fields to document_requirements

Revision ID: 20260320_0017
Revises: 20260320_0016
Create Date: 2026-03-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260320_0017"
down_revision = "20260320_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("document_requirements")}
    indexes = {idx["name"] for idx in inspector.get_indexes("document_requirements")}

    with op.batch_alter_table("document_requirements", schema=None) as batch_op:
        if "code" not in columns:
            batch_op.add_column(sa.Column("code", sa.String(length=80), nullable=True))
        if "title" not in columns:
            batch_op.add_column(sa.Column("title", sa.String(length=200), nullable=True))
        if "frequency" not in columns:
            batch_op.add_column(
                sa.Column("frequency", sa.String(length=20), nullable=False, server_default="MONTHLY")
            )
        if "is_required" not in columns:
            batch_op.add_column(
                sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("1"))
            )
        if "display_order" not in columns:
            batch_op.add_column(
                sa.Column("display_order", sa.Integer(), nullable=False, server_default="0")
            )
        if "due_rule_text" not in columns:
            batch_op.add_column(sa.Column("due_rule_text", sa.String(length=255), nullable=True))
        if "note" not in columns:
            batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))

        batch_op.alter_column("site_id", existing_type=sa.Integer(), nullable=True)

    if "ix_document_requirements_code" not in indexes:
        op.create_index("ix_document_requirements_code", "document_requirements", ["code"], unique=False)

    # Backfill with document type defaults to keep legacy rows valid.
    op.execute(
        """
        UPDATE document_requirements
        SET code = (
            SELECT dt.code FROM document_type_masters dt WHERE dt.id = document_requirements.document_type_id
        )
        WHERE code IS NULL
        """
    )
    op.execute(
        """
        UPDATE document_requirements
        SET title = (
            SELECT dt.name FROM document_type_masters dt WHERE dt.id = document_requirements.document_type_id
        )
        WHERE title IS NULL
        """
    )
    op.execute("UPDATE document_requirements SET frequency = COALESCE(frequency, 'MONTHLY')")
    op.execute("UPDATE document_requirements SET is_required = COALESCE(is_required, 1)")
    op.execute("UPDATE document_requirements SET display_order = COALESCE(display_order, 0)")

    with op.batch_alter_table("document_requirements", schema=None) as batch_op:
        batch_op.alter_column("code", existing_type=sa.String(length=80), nullable=False)
        batch_op.alter_column("title", existing_type=sa.String(length=200), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("document_requirements")}
    indexes = {idx["name"] for idx in inspector.get_indexes("document_requirements")}

    if "ix_document_requirements_code" in indexes:
        op.drop_index("ix_document_requirements_code", table_name="document_requirements")

    with op.batch_alter_table("document_requirements", schema=None) as batch_op:
        if "note" in columns:
            batch_op.drop_column("note")
        if "due_rule_text" in columns:
            batch_op.drop_column("due_rule_text")
        if "display_order" in columns:
            batch_op.drop_column("display_order")
        if "is_required" in columns:
            batch_op.drop_column("is_required")
        if "frequency" in columns:
            batch_op.drop_column("frequency")
        if "title" in columns:
            batch_op.drop_column("title")
        if "code" in columns:
            batch_op.drop_column("code")
        batch_op.alter_column("site_id", existing_type=sa.Integer(), nullable=False)
