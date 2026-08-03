"""inspection journals and cropped evidence photos

Revision ID: 20260803_0078
Revises: 20260629_0077
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260803_0078"
down_revision = "20260629_0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "inspection_journals" not in tables:
        op.create_table(
            "inspection_journals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("site_name", sa.String(length=200), nullable=False),
            sa.Column("subject", sa.String(length=300), nullable=False),
            sa.Column("inspected_on", sa.Date(), nullable=False),
            sa.Column("time_text", sa.String(length=100), nullable=True),
            sa.Column("location", sa.String(length=300), nullable=True),
            sa.Column("attendees", sa.Text(), nullable=True),
            sa.Column("instructor_name", sa.String(length=100), nullable=True),
            sa.Column("instructor_affiliation", sa.String(length=200), nullable=True),
            sa.Column("training_code", sa.String(length=50), nullable=False),
            sa.Column("training_label", sa.String(length=150), nullable=False),
            sa.Column("legal_content", sa.Text(), nullable=False),
            sa.Column("additional_content", sa.Text(), nullable=True),
            sa.Column("special_notes", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_by_name", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_inspection_journals_site_name", "inspection_journals", ["site_name"])
        op.create_index("ix_inspection_journals_inspected_on", "inspection_journals", ["inspected_on"])
        op.create_index("ix_inspection_journals_training_code", "inspection_journals", ["training_code"])
        op.create_index("ix_inspection_journals_created_by_user_id", "inspection_journals", ["created_by_user_id"])
        op.create_index("ix_inspection_journals_created_at", "inspection_journals", ["created_at"])

    inspector = sa.inspect(bind)
    if "inspection_journal_photos" not in inspector.get_table_names():
        op.create_table(
            "inspection_journal_photos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("journal_id", sa.Integer(), nullable=False),
            sa.Column("image_path", sa.String(length=500), nullable=False),
            sa.Column("original_name", sa.String(length=255), nullable=False),
            sa.Column("caption", sa.String(length=500), nullable=True),
            sa.Column("rotation_degrees", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("crop_left", sa.Float(), nullable=False, server_default="0"),
            sa.Column("crop_top", sa.Float(), nullable=False, server_default="0"),
            sa.Column("crop_right", sa.Float(), nullable=False, server_default="0"),
            sa.Column("crop_bottom", sa.Float(), nullable=False, server_default="0"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["journal_id"], ["inspection_journals.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_inspection_journal_photos_journal_id", "inspection_journal_photos", ["journal_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "inspection_journal_photos" in tables:
        op.drop_index("ix_inspection_journal_photos_journal_id", table_name="inspection_journal_photos")
        op.drop_table("inspection_journal_photos")
    if "inspection_journals" in tables:
        op.drop_index("ix_inspection_journals_created_at", table_name="inspection_journals")
        op.drop_index("ix_inspection_journals_created_by_user_id", table_name="inspection_journals")
        op.drop_index("ix_inspection_journals_training_code", table_name="inspection_journals")
        op.drop_index("ix_inspection_journals_inspected_on", table_name="inspection_journals")
        op.drop_index("ix_inspection_journals_site_name", table_name="inspection_journals")
        op.drop_table("inspection_journals")
