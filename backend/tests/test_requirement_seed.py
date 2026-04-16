from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.sites.models import Site
from app.seeds.seed_requirements_samsung_additional import (
    PERIOD_MAP,
    apply_missing_requirements,
    compute_missing_requirements,
    current_requirement_titles,
    samsung_requirement_specs,
)


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.document_settings import models as doc_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _seed_basics(db):
    db.add(Site(site_code="SITE001", site_name="테스트 현장", status="ACTIVE"))
    db.add(Site(site_code="SITE002", site_name="테스트 현장2", status="ACTIVE"))
    db.flush()
    daily = SubmissionCycle(code="DAILY", name="일간", sort_order=10, is_auto_generatable=True)
    monthly = SubmissionCycle(code="MONTHLY", name="월간", sort_order=30, is_auto_generatable=True)
    adhoc = SubmissionCycle(code="ADHOC", name="수시", sort_order=90, is_auto_generatable=False)
    db.add_all([daily, monthly, adhoc])
    db.flush()
    db.add(
        DocumentTypeMaster(
            code="LEGAL_DOC",
            name="법정서류",
            default_cycle_id=adhoc.id,
            generation_rule="ADHOC_MANUAL",
            is_required_default=False,
        )
    )
    db.add(
        DocumentTypeMaster(
            code="DAILY_DOC",
            name="일상점검",
            default_cycle_id=daily.id,
            generation_rule="DAILY",
            is_required_default=True,
        )
    )
    db.commit()


def test_samsung_seed_inserts_expected_titles():
    db = _setup_db()
    _seed_basics(db)

    missing = compute_missing_requirements(current_requirement_titles(db))
    added = apply_missing_requirements(db, missing)

    expected_titles = {spec.title for spec in samsung_requirement_specs()}
    actual_titles = {
        title
        for (title,) in db.query(DocumentRequirement.title).filter(DocumentRequirement.title.in_(expected_titles)).all()
    }
    assert len(added) == len(expected_titles)
    assert len(actual_titles) >= len(expected_titles)


def test_samsung_seed_does_not_create_duplicates_by_title_per_site():
    db = _setup_db()
    _seed_basics(db)

    first_missing = compute_missing_requirements(current_requirement_titles(db))
    apply_missing_requirements(db, first_missing)
    second_missing = compute_missing_requirements(current_requirement_titles(db))
    second_added = apply_missing_requirements(db, second_missing)

    assert second_added == []

    for spec in samsung_requirement_specs():
        counts = (
            db.query(DocumentRequirement.site_id, DocumentRequirement.id)
            .filter(DocumentRequirement.title == spec.title)
            .all()
        )
        by_site: dict[int, int] = {}
        for site_id, _ in counts:
            by_site[site_id] = by_site.get(site_id, 0) + 1
        assert all(c == 1 for c in by_site.values())


def test_samsung_seed_period_mapping_is_correct():
    specs = samsung_requirement_specs()
    by_title = {spec.title: spec.period for spec in specs}

    assert by_title["일일안전회의록 및 위험성평가"] == PERIOD_MAP["매일"]
    assert by_title["소통회의 결과보고서"] == PERIOD_MAP["월1회"]
    assert by_title["비상사태 매뉴얼"] == PERIOD_MAP["발생시"]
