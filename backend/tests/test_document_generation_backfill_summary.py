from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.document_settings.models import DocumentTypeMaster, SubmissionCycle
from app.modules.document_generation.routes import backfill_document_instances
from app.schemas.document_generation import BackfillRequest


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.documents.models import Document  # noqa: F401
    from app.modules.document_generation.models import DocumentInstance  # noqa: F401
    from app.modules.document_settings.models import DocumentRequirement  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        site = Site(site_code="S1", site_name="S1")
        session.add(site)
        session.commit()
        user = User(id=1, name="system", login_id="system", password_hash="x", site_id=site.id)
        session.add(user)
        session.commit()
        yield session
    finally:
        session.close()


def _add_cycle(db, code: str) -> SubmissionCycle:
    c = SubmissionCycle(
        code=code,
        name=code,
        sort_order=0,
        is_active=True,
        is_auto_generatable=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _add_doc_type(db, code: str, default_cycle_id: int) -> DocumentTypeMaster:
    dt = DocumentTypeMaster(
        code=code,
        name=code,
        description=None,
        sort_order=0,
        is_active=True,
        default_cycle_id=default_cycle_id,
        generation_rule="ON_PERIOD_START",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return dt


def test_backfill_summary_counts_match_detail_lists(db):
    daily = _add_cycle(db, "DAILY")
    _add_doc_type(db, "DAILY_DOC", daily.id)

    payload = BackfillRequest(
        site_id=1,
        start_date=date(2026, 3, 17),
        end_date=date(2026, 3, 17),
        dry_run=True,
        retry_failed=False,
        reevaluate_skipped=False,
        document_type_codes=None,
    )

    resp = backfill_document_instances(payload=payload, db=db, __=None)
    summary = resp["summary"]

    assert summary["created"] == len(resp["created"])
    assert summary["failed"] == len(resp["failed"])
    assert summary["skipped"] == len(resp["skipped"])
    assert (summary["created"] + summary["failed"] + summary["skipped"]) == 1

