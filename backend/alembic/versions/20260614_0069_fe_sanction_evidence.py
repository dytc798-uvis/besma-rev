"""기능인제 제재 — 근거(사진·코멘트)·서명·감점

Revision ID: 20260614_0069
Revises: 20260614_0068
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0069"
down_revision = "20260614_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "functional_eval_sanctions",
        sa.Column("evidence_type", sa.String(length=20), nullable=False, server_default="COMMENT"),
    )
    op.add_column(
        "functional_eval_sanctions",
        sa.Column("evidence_photo_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "functional_eval_sanctions",
        sa.Column("evidence_photo_original_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "functional_eval_sanctions",
        sa.Column("signature_data", sa.Text(), nullable=True),
    )
    op.add_column(
        "functional_eval_sanctions",
        sa.Column("signature_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "functional_eval_sanctions",
        sa.Column("penalty_points", sa.Integer(), nullable=False, server_default="5"),
    )


def downgrade() -> None:
    op.drop_column("functional_eval_sanctions", "penalty_points")
    op.drop_column("functional_eval_sanctions", "signature_hash")
    op.drop_column("functional_eval_sanctions", "signature_data")
    op.drop_column("functional_eval_sanctions", "evidence_photo_original_filename")
    op.drop_column("functional_eval_sanctions", "evidence_photo_path")
    op.drop_column("functional_eval_sanctions", "evidence_type")
