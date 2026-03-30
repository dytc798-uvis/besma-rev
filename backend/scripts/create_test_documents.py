from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func

BACKEND_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.modules.document_generation.models import (
    DocumentInstance,
    DocumentInstanceStatus,
    PeriodBasis,
    WorkflowStatus,
)
from app.modules.document_settings.models import DocumentTypeMaster
from app.modules.documents.models import Document, DocumentStatus
from app.modules.sites.models import Site
from app.modules.users.models import User


def _resolve_site_and_submitter(db) -> tuple[Site, User]:
    site = db.query(Site).order_by(Site.id.asc()).first()
    if site is None:
        site = Site(site_code="S-TEST-DOC-001", site_name="테스트 문서 현장")
        db.add(site)
        db.flush()

    user = db.query(User).filter(User.site_id == site.id).order_by(User.id.asc()).first()
    if user is None:
        next_id = int(db.query(func.coalesce(func.max(User.id), 0)).scalar() or 0) + 1
        user = User(
            id=next_id,
            name="doc-seed-user",
            login_id=f"doc_seed_{next_id}",
            password_hash="seed-temp",
            site_id=site.id,
            role=Role.SITE,
        )
        db.add(user)
        db.flush()
    return site, user


def run() -> None:
    db = SessionLocal()
    try:
        site, submitter = _resolve_site_and_submitter(db)
        today = date.today()
        types = (
            db.query(DocumentTypeMaster)
            .filter(DocumentTypeMaster.is_active.is_(True))
            .order_by(DocumentTypeMaster.sort_order.asc())
            .limit(3)
            .all()
        )
        if not types:
            print("No active document types found in document_type_masters.")
            return

        created_instances = 0
        created_documents = 0
        for dt in types:
            instance = (
                db.query(DocumentInstance)
                .filter(
                    DocumentInstance.site_id == site.id,
                    DocumentInstance.document_type_code == dt.code,
                    DocumentInstance.period_basis == PeriodBasis.AS_OF_FALLBACK,
                    DocumentInstance.period_start == today,
                    DocumentInstance.period_end == today,
                )
                .first()
            )
            if instance is None:
                instance = DocumentInstance(
                    site_id=site.id,
                    document_type_code=dt.code,
                    period_start=today,
                    period_end=today,
                    generation_anchor_date=today,
                    due_date=today,
                    status=DocumentInstanceStatus.GENERATED,
                    status_reason="MANUAL_SCRIPT",
                    selected_requirement_id=None,
                    workflow_status=WorkflowStatus.NOT_SUBMITTED,
                    period_basis=PeriodBasis.AS_OF_FALLBACK,
                    rule_is_required=True,
                    cycle_code="ADHOC",
                    rule_generation_rule="MANUAL_SCRIPT",
                    rule_generation_value=None,
                    rule_due_offset_days=0,
                    resolved_from="MANUAL_SCRIPT",
                    resolved_cycle_source="manual",
                    master_cycle_id=None,
                    master_cycle_code="ADHOC",
                    override_cycle_id=None,
                    override_cycle_code=None,
                    error_message=None,
                )
                db.add(instance)
                db.flush()
                created_instances += 1

            doc = db.query(Document).filter(Document.instance_id == instance.id).first()
            if doc is None:
                doc = Document(
                    document_no=f"SEED-{instance.id}-{int(utc_now().timestamp())}",
                    title=f"[SEED] {dt.name} {today.isoformat()}",
                    document_type=dt.code,
                    site_id=site.id,
                    submitter_user_id=submitter.id,
                    current_status=DocumentStatus.DRAFT,
                    description="테스트 문서 생성 스크립트",
                    source_type="MANUAL",
                    period_start=today,
                    period_end=today,
                    due_date=today,
                    instance_id=instance.id,
                )
                db.add(doc)
                created_documents += 1

        db.commit()
        instance_count = db.query(DocumentInstance).count()
        document_count = db.query(Document).count()
        print(f"site_id={site.id}, submitter_user_id={submitter.id}")
        print(f"created_instances={created_instances}, created_documents={created_documents}")
        print(f"total_instances={instance_count}, total_documents={document_count}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
