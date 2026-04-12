"""upload asset derivative paths

Revision ID: 20260412_0027
Revises: 20260412_0026
Create Date: 2026-04-12 16:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260412_0027"
down_revision = "20260412_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    document_cols = {c["name"] for c in inspector.get_columns("documents")}
    if "original_file_path" not in document_cols:
        op.add_column("documents", sa.Column("original_file_path", sa.String(length=500), nullable=True))
    if "optimized_file_path" not in document_cols:
        op.add_column("documents", sa.Column("optimized_file_path", sa.String(length=500), nullable=True))

    communication_cols = {c["name"] for c in inspector.get_columns("communications")}
    if "bundle_pdf_path" not in communication_cols:
        op.add_column("communications", sa.Column("bundle_pdf_path", sa.String(length=500), nullable=True))

    attachment_cols = {c["name"] for c in inspector.get_columns("communication_attachments")}
    if "original_file_path" not in attachment_cols:
        op.add_column(
            "communication_attachments",
            sa.Column("original_file_path", sa.String(length=500), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    document_cols = {c["name"] for c in inspector.get_columns("documents")}
    if "optimized_file_path" in document_cols:
        op.drop_column("documents", "optimized_file_path")
    if "original_file_path" in document_cols:
        op.drop_column("documents", "original_file_path")

    communication_cols = {c["name"] for c in inspector.get_columns("communications")}
    if "bundle_pdf_path" in communication_cols:
        op.drop_column("communications", "bundle_pdf_path")

    attachment_cols = {c["name"] for c in inspector.get_columns("communication_attachments")}
    if "original_file_path" in attachment_cols:
        op.drop_column("communication_attachments", "original_file_path")
