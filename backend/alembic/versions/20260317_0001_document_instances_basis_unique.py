"""document_instances: add period_basis and unique constraint

- 기존/운영 SQLite DB에 대해 재생성 없이 스키마 업그레이드를 보장한다.
- SQLite는 제약 변경이 제한적이므로, batch(recreate) 방식으로 테이블을 리빌드한다.

Revision ID: 20260317_0001
Revises: 
Create Date: 2026-03-17

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # pre-alembic 레거시 DB가 아닌 clean DB에서도 체인이 동작하도록
    # 문서/작업자/설정 핵심 테이블을 최소 스키마로 보장한다.
    table_names = set(insp.get_table_names())

    if "sites" not in table_names:
        op.create_table(
            "sites",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("site_code", sa.String(length=50), nullable=False, unique=True),
            sa.Column("site_name", sa.String(length=200), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("client_name", sa.String(length=200), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("manager_name", sa.String(length=100), nullable=True),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_sites_id", "sites", ["id"], unique=False)
        op.create_index("ix_sites_site_code", "sites", ["site_code"], unique=True)

    table_names = set(sa.inspect(bind).get_table_names())
    if "users" not in table_names:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("login_id", sa.String(length=50), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("birth_date", sa.Date(), nullable=True),
            sa.Column("department", sa.String(length=100), nullable=True),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("ui_type", sa.String(length=20), nullable=False),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_users_id", "users", ["id"], unique=False)
        op.create_index("ix_users_login_id", "users", ["login_id"], unique=True)

    table_names = set(sa.inspect(bind).get_table_names())
    if "documents" not in table_names:
        op.create_table(
            "documents",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("document_no", sa.String(length=50), nullable=False, unique=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("document_type", sa.String(length=50), nullable=False),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
            sa.Column("submitter_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("current_status", sa.String(length=20), nullable=False),
            sa.Column("file_path", sa.String(length=500), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_documents_id", "documents", ["id"], unique=False)
        op.create_index("ix_documents_document_no", "documents", ["document_no"], unique=True)

    table_names = set(sa.inspect(bind).get_table_names())
    if "persons" not in table_names:
        op.create_table(
            "persons",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("birth_date", sa.Date(), nullable=True),
            sa.Column("rrn_hash", sa.String(length=128), nullable=True),
            sa.Column("rrn_masked", sa.String(length=20), nullable=True),
            sa.Column("phone_mobile", sa.String(length=20), nullable=True),
            sa.Column("email", sa.String(length=200), nullable=True),
            sa.Column("is_foreigner", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("nationality", sa.String(length=10), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_persons_id", "persons", ["id"], unique=False)
        op.create_index("ix_persons_rrn_hash", "persons", ["rrn_hash"], unique=False)
        op.create_index("ix_persons_phone_mobile", "persons", ["phone_mobile"], unique=False)

    table_names = set(sa.inspect(bind).get_table_names())
    if "employments" not in table_names:
        op.create_table(
            "employments",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("person_id", sa.Integer(), sa.ForeignKey("persons.id"), nullable=False),
            sa.Column("source_type", sa.String(length=20), nullable=False),
            sa.Column("employee_code", sa.String(length=50), nullable=True),
            sa.Column("department_code", sa.String(length=50), nullable=True),
            sa.Column("department_name", sa.String(length=100), nullable=True),
            sa.Column("position_code", sa.String(length=50), nullable=True),
            sa.Column("position_name", sa.String(length=100), nullable=True),
            sa.Column("hire_date", sa.Date(), nullable=True),
            sa.Column("termination_date", sa.Date(), nullable=True),
            sa.Column("site_code", sa.String(length=50), nullable=True),
            sa.Column("job_code", sa.String(length=50), nullable=True),
            sa.Column("daily_wage", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_employments_id", "employments", ["id"], unique=False)

    table_names = set(sa.inspect(bind).get_table_names())
    if "worker_import_batches" not in table_names:
        op.create_table(
            "worker_import_batches",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("source_type", sa.String(length=50), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("stored_path", sa.String(length=500), nullable=False),
            sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("warning_summary", sa.String(length=1000), nullable=True),
            sa.Column("diff_new_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("diff_updated_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("diff_unchanged_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_worker_import_batches_id", "worker_import_batches", ["id"], unique=False)

    table_names = set(sa.inspect(bind).get_table_names())
    if "submission_cycles" not in table_names:
        op.create_table(
            "submission_cycles",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("code", sa.String(length=50), nullable=False, unique=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column(
                "is_auto_generatable",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_submission_cycles_id", "submission_cycles", ["id"], unique=False)
        op.create_index("ix_submission_cycles_code", "submission_cycles", ["code"], unique=True)

    table_names = set(sa.inspect(bind).get_table_names())
    if "document_type_masters" not in table_names:
        op.create_table(
            "document_type_masters",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("code", sa.String(length=50), nullable=False, unique=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column(
                "default_cycle_id",
                sa.Integer(),
                sa.ForeignKey("submission_cycles.id"),
                nullable=False,
            ),
            sa.Column("generation_rule", sa.String(length=50), nullable=True),
            sa.Column("generation_value", sa.String(length=100), nullable=True),
            sa.Column("due_offset_days", sa.Integer(), nullable=True),
            sa.Column("is_required_default", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_document_type_masters_id",
            "document_type_masters",
            ["id"],
            unique=False,
        )
        op.create_index(
            "ix_document_type_masters_code",
            "document_type_masters",
            ["code"],
            unique=True,
        )

    table_names = set(sa.inspect(bind).get_table_names())
    if "document_requirements" not in table_names:
        op.create_table(
            "document_requirements",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
            sa.Column(
                "document_type_id",
                sa.Integer(),
                sa.ForeignKey("document_type_masters.id"),
                nullable=False,
            ),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column(
                "override_cycle_id",
                sa.Integer(),
                sa.ForeignKey("submission_cycles.id"),
                nullable=True,
            ),
            sa.Column("override_generation_rule", sa.String(length=50), nullable=True),
            sa.Column("override_generation_value", sa.String(length=100), nullable=True),
            sa.Column("override_due_offset_days", sa.Integer(), nullable=True),
            sa.Column("effective_from", sa.Date(), nullable=True),
            sa.Column("effective_to", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_document_requirements_id",
            "document_requirements",
            ["id"],
            unique=False,
        )
        op.create_index(
            "ix_document_requirements_site_id",
            "document_requirements",
            ["site_id"],
            unique=False,
        )
        op.create_index(
            "ix_document_requirements_document_type_id",
            "document_requirements",
            ["document_type_id"],
            unique=False,
        )

    insp = sa.inspect(bind)
    if "document_instances" not in insp.get_table_names():
        # 신규 설치: ORM create_all이 생성할 수 있으나, 마이그레이션만으로도 테이블을 생성 가능하게 둔다.
        op.create_table(
            "document_instances",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False, index=True),
            sa.Column("document_type_code", sa.String(length=50), nullable=False, index=True),
            sa.Column("period_basis", sa.String(length=30), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False, index=True),
            sa.Column("period_end", sa.Date(), nullable=False, index=True),
            sa.Column("generation_anchor_date", sa.Date(), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, index=True),
            sa.Column("status_reason", sa.String(length=50), nullable=False),
            sa.Column("selected_requirement_id", sa.Integer(), nullable=True),
            sa.Column("rule_is_required", sa.Boolean(), nullable=False),
            sa.Column("cycle_code", sa.String(length=20), nullable=True),
            sa.Column("rule_generation_rule", sa.String(length=50), nullable=True),
            sa.Column("rule_generation_value", sa.String(length=50), nullable=True),
            sa.Column("rule_due_offset_days", sa.Integer(), nullable=True),
            sa.Column("resolved_from", sa.String(length=20), nullable=True),
            sa.Column("resolved_cycle_source", sa.String(length=20), nullable=True),
            sa.Column("master_cycle_id", sa.Integer(), nullable=True),
            sa.Column("master_cycle_code", sa.String(length=20), nullable=True),
            sa.Column("override_cycle_id", sa.Integer(), nullable=True),
            sa.Column("override_cycle_code", sa.String(length=20), nullable=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True, index=True),
            sa.Column("error_message", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "site_id",
                "document_type_code",
                "period_basis",
                "period_start",
                "period_end",
                name="uq_document_instances_site_type_basis_period",
            ),
        )
        return

    # 기존 DB: SQLite batch(recreate) 방식으로 컬럼/제약을 업그레이드
    with op.batch_alter_table("document_instances", recreate="always") as batch:
        cols = {c["name"] for c in insp.get_columns("document_instances")}

        # 1) period_basis (NOT NULL).
        # 기존 데이터의 생성 맥락을 100% 안전하게 재현하기 어렵기 때문에,
        # "cycle_code IS NULL" 같은 불완전한 추정으로 AS_OF_FALLBACK로 바꾸지 않는다.
        # 보수적으로 기존 row는 모두 CYCLE로 유지하고, 필요 시 별도 데이터 정비 절차로 분리한다.
        if "period_basis" not in cols:
            batch.add_column(
                sa.Column(
                    "period_basis",
                    sa.String(length=30),
                    nullable=False,
                    server_default="CYCLE",
                )
            )

        # 2) snapshot/운영 필드들 (없으면 추가)
        def add_if_missing(name: str, col: sa.Column) -> None:
            if name not in cols:
                batch.add_column(col)

        add_if_missing("rule_is_required", sa.Column("rule_is_required", sa.Boolean(), nullable=False, server_default="0"))
        add_if_missing("resolved_from", sa.Column("resolved_from", sa.String(length=20), nullable=True))
        add_if_missing("resolved_cycle_source", sa.Column("resolved_cycle_source", sa.String(length=20), nullable=True))
        add_if_missing("master_cycle_id", sa.Column("master_cycle_id", sa.Integer(), nullable=True))
        add_if_missing("master_cycle_code", sa.Column("master_cycle_code", sa.String(length=20), nullable=True))
        add_if_missing("override_cycle_id", sa.Column("override_cycle_id", sa.Integer(), nullable=True))
        add_if_missing("override_cycle_code", sa.Column("override_cycle_code", sa.String(length=20), nullable=True))

        # 3) 유니크 제약을 basis 포함으로 고정
        batch.create_unique_constraint(
            "uq_document_instances_site_type_basis_period",
            ["site_id", "document_type_code", "period_basis", "period_start", "period_end"],
        )

    # 데이터 보정은 수행하지 않는다(의미 보존 우선).


def downgrade() -> None:
    # 다운그레이드는 운영상 필요성이 낮아 no-op 처리
    pass

