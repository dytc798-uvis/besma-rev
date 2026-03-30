from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.document_settings.constants import RuleStatusReason
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.document_settings.service import get_effective_rule


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # Register referenced tables (FK targets) before create_all
    from app.modules.sites.models import Site  # noqa: F401
    from app.modules.users.models import User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _add_cycle(db, code: str, is_active: bool = True, is_auto: bool = True) -> SubmissionCycle:
    c = SubmissionCycle(
        code=code,
        name=code,
        sort_order=0,
        is_active=is_active,
        is_auto_generatable=is_auto,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _add_doc_type(db, code: str, default_cycle_id: int, is_active: bool = True) -> DocumentTypeMaster:
    dt = DocumentTypeMaster(
        code=code,
        name=code,
        description=None,
        sort_order=0,
        is_active=is_active,
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


def _assert_generation_none(rule):
    assert rule.generation_rule is None
    assert rule.generation_value is None
    assert rule.due_offset_days is None


def test_doc_type_missing_contract(db):
    rule = get_effective_rule(db=db, site_id=1, document_type_code="DAILY_DOC", as_of_date=date(2026, 3, 17))
    assert rule is not None
    assert rule.status_reason == RuleStatusReason.DOC_TYPE_INACTIVE_OR_MISSING
    assert rule.is_required is False
    assert rule.cycle is None
    _assert_generation_none(rule)
    assert rule.selected_requirement_id is None


def test_site_disabled_contract(db):
    daily = _add_cycle(db, "DAILY", is_active=True, is_auto=True)
    dt = _add_doc_type(db, "DAILY_DOC", default_cycle_id=daily.id, is_active=True)

    req = DocumentRequirement(
        site_id=1,
        document_type_id=dt.id,
        is_enabled=False,
        override_cycle_id=None,
        override_generation_rule="ON_DAY_OF_PERIOD",  # should be ignored due to hard disable
        override_generation_value="2",
        override_due_offset_days=3,
        effective_from=None,
        effective_to=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    rule = get_effective_rule(db=db, site_id=1, document_type_code="DAILY_DOC", as_of_date=date(2026, 3, 17))
    assert rule.status_reason == RuleStatusReason.SITE_DISABLED
    assert rule.is_required is False
    assert rule.cycle is None
    _assert_generation_none(rule)
    assert rule.selected_requirement_id == req.id


def test_cycle_inactive_contract_cycle_none(db):
    inactive = _add_cycle(db, "MONTHLY", is_active=False, is_auto=True)
    _add_doc_type(db, "DAILY_DOC", default_cycle_id=inactive.id, is_active=True)

    rule = get_effective_rule(db=db, site_id=1, document_type_code="DAILY_DOC", as_of_date=date(2026, 3, 17))
    assert rule.status_reason == RuleStatusReason.CYCLE_INACTIVE
    assert rule.is_required is False
    assert rule.cycle is None
    _assert_generation_none(rule)
    assert rule.selected_requirement_id is None


def test_cycle_inactive_contract_selected_requirement_id_when_requirement_exists(db):
    inactive = _add_cycle(db, "MONTHLY", is_active=False, is_auto=True)
    dt = _add_doc_type(db, "DAILY_DOC", default_cycle_id=inactive.id, is_active=True)

    req = DocumentRequirement(
        site_id=1,
        document_type_id=dt.id,
        is_enabled=True,
        override_cycle_id=None,
        override_generation_rule=None,
        override_generation_value=None,
        override_due_offset_days=None,
        effective_from=None,
        effective_to=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    rule = get_effective_rule(db=db, site_id=1, document_type_code="DAILY_DOC", as_of_date=date(2026, 3, 17))
    assert rule.status_reason == RuleStatusReason.CYCLE_INACTIVE
    assert rule.is_required is False
    assert rule.cycle is None
    _assert_generation_none(rule)
    assert rule.selected_requirement_id == req.id


def test_cycle_manual_only_contract(db):
    adhoc = _add_cycle(db, "ADHOC", is_active=True, is_auto=False)
    _add_doc_type(db, "DAILY_DOC", default_cycle_id=adhoc.id, is_active=True)

    rule = get_effective_rule(db=db, site_id=1, document_type_code="DAILY_DOC", as_of_date=date(2026, 3, 17))
    assert rule.status_reason == RuleStatusReason.CYCLE_MANUAL_ONLY
    assert rule.is_required is False
    assert rule.cycle == "ADHOC"
    _assert_generation_none(rule)
    assert rule.selected_requirement_id is None


def test_cycle_manual_only_contract_selected_requirement_id_when_requirement_exists(db):
    adhoc = _add_cycle(db, "ADHOC", is_active=True, is_auto=False)
    dt = _add_doc_type(db, "DAILY_DOC", default_cycle_id=adhoc.id, is_active=True)

    req = DocumentRequirement(
        site_id=1,
        document_type_id=dt.id,
        is_enabled=True,
        override_cycle_id=None,
        override_generation_rule=None,
        override_generation_value=None,
        override_due_offset_days=None,
        effective_from=None,
        effective_to=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    rule = get_effective_rule(db=db, site_id=1, document_type_code="DAILY_DOC", as_of_date=date(2026, 3, 17))
    assert rule.status_reason == RuleStatusReason.CYCLE_MANUAL_ONLY
    assert rule.is_required is False
    assert rule.cycle == "ADHOC"
    _assert_generation_none(rule)
    assert rule.selected_requirement_id == req.id


def test_master_default_success_contract(db):
    daily = _add_cycle(db, "DAILY", is_active=True, is_auto=True)
    _add_doc_type(db, "DAILY_DOC", default_cycle_id=daily.id, is_active=True)

    rule = get_effective_rule(db=db, site_id=1, document_type_code="DAILY_DOC", as_of_date=date(2026, 3, 17))
    assert rule.status_reason == RuleStatusReason.MASTER_DEFAULT
    assert rule.is_required is True
    assert rule.cycle == "DAILY"
    assert rule.generation_rule is not None
    assert rule.due_offset_days is not None
    assert rule.selected_requirement_id is None


def test_site_override_success_contract_selected_id(db):
    daily = _add_cycle(db, "DAILY", is_active=True, is_auto=True)
    weekly = _add_cycle(db, "WEEKLY", is_active=True, is_auto=True)
    dt = _add_doc_type(db, "DAILY_DOC", default_cycle_id=daily.id, is_active=True)

    req = DocumentRequirement(
        site_id=1,
        document_type_id=dt.id,
        is_enabled=True,
        override_cycle_id=weekly.id,
        override_generation_rule=None,
        override_generation_value=None,
        override_due_offset_days=None,
        effective_from=None,
        effective_to=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    rule = get_effective_rule(db=db, site_id=1, document_type_code="DAILY_DOC", as_of_date=date(2026, 3, 17))
    assert rule.status_reason == RuleStatusReason.SITE_OVERRIDE
    assert rule.is_required is True
    assert rule.cycle == "WEEKLY"
    assert rule.selected_requirement_id == req.id

