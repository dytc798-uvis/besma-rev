"""force daily checklist frequencies and add site manager checklist requirement

Revision ID: 20260416_0034
Revises: 20260416_0033
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260416_0034"
down_revision = "20260416_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "document_requirements" not in tables:
        return
    requirement_columns = {col["name"] for col in inspector.get_columns("document_requirements")}
    has_created_at = "created_at" in requirement_columns
    has_updated_at = "updated_at" in requirement_columns
    timestamp_cols = ""
    timestamp_vals = ""
    if has_created_at:
        timestamp_cols += ", created_at"
        timestamp_vals += ", CURRENT_TIMESTAMP"
    if has_updated_at:
        timestamp_cols += ", updated_at"
        timestamp_vals += ", CURRENT_TIMESTAMP"

    op.execute(
        sa.text(
            """
            UPDATE document_requirements
            SET frequency = 'DAILY',
                due_rule_text = CASE
                    WHEN code = 'SUPERVISOR_CHECKLIST' THEN '일 1회 업로드 (점검 완료 후)'
                    WHEN code = 'SAFETY_MANAGER_DAILY_LOG' THEN '일 1회 업로드 (업무 종료 후)'
                    ELSE due_rule_text
                END
            WHERE code IN ('SUPERVISOR_CHECKLIST', 'SAFETY_MANAGER_DAILY_LOG')
            """
        )
    )

    if "sites" not in tables or "document_type_masters" not in tables:
        return

    site_rows = bind.execute(sa.text("SELECT id FROM sites")).fetchall()
    if not site_rows:
        return
    site_ids = [int(row[0]) for row in site_rows]

    inspection_type_id = bind.execute(
        sa.text("SELECT id FROM document_type_masters WHERE code = 'INSPECTION' LIMIT 1")
    ).scalar()
    if inspection_type_id is None:
        return

    existing_site_manager_sites = {
        int(row[0])
        for row in bind.execute(
            sa.text("SELECT site_id FROM document_requirements WHERE code = 'SITE_MANAGER_CHECKLIST'")
        ).fetchall()
    }
    existing_safety_sites = {
        int(row[0])
        for row in bind.execute(
            sa.text("SELECT site_id FROM document_requirements WHERE code = 'SAFETY_MANAGER_DAILY_LOG'")
        ).fetchall()
    }

    for site_id in site_ids:
        if site_id not in existing_site_manager_sites:
            max_order = bind.execute(
                sa.text(
                    "SELECT COALESCE(MAX(display_order), 0) FROM document_requirements WHERE site_id = :site_id"
                ),
                {"site_id": site_id},
            ).scalar()
            bind.execute(
                sa.text(
                    """
                    INSERT INTO document_requirements
                    (site_id, document_type_id, code, title, frequency, is_required, is_enabled, display_order, due_rule_text, note{created_cols})
                    VALUES
                    (:site_id, :document_type_id, 'SITE_MANAGER_CHECKLIST', '현장소장 점검표', 'DAILY', 1, 1, :display_order, '일 1회 업로드 (점검 완료 후)', NULL{created_vals})
                    """
                    .format(
                        created_cols=timestamp_cols,
                        created_vals=timestamp_vals,
                    )
                ),
                {
                    "site_id": site_id,
                    "document_type_id": int(inspection_type_id),
                    "display_order": int(max_order) + 1,
                },
            )
        if site_id not in existing_safety_sites:
            max_order = bind.execute(
                sa.text(
                    "SELECT COALESCE(MAX(display_order), 0) FROM document_requirements WHERE site_id = :site_id"
                ),
                {"site_id": site_id},
            ).scalar()
            bind.execute(
                sa.text(
                    """
                    INSERT INTO document_requirements
                    (site_id, document_type_id, code, title, frequency, is_required, is_enabled, display_order, due_rule_text, note{created_cols})
                    VALUES
                    (:site_id, :document_type_id, 'SAFETY_MANAGER_DAILY_LOG', '안전관리자 업무일지', 'DAILY', 1, 1, :display_order, '일 1회 업로드 (업무 종료 후)', NULL{created_vals})
                    """
                    .format(
                        created_cols=timestamp_cols,
                        created_vals=timestamp_vals,
                    )
                ),
                {
                    "site_id": site_id,
                    "document_type_id": int(inspection_type_id),
                    "display_order": int(max_order) + 1,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "document_requirements" not in tables:
        return

    op.execute(
        sa.text(
            """
            DELETE FROM document_requirements
            WHERE code IN ('SITE_MANAGER_CHECKLIST', 'SAFETY_MANAGER_DAILY_LOG')
            """
        )
    )
