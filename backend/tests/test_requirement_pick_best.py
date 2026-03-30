from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.document_settings.service import _pick_best_requirement, _list_valid_requirements


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.sites.models import Site  # noqa: F401
    from app.modules.users.models import User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _add_cycle(db) -> SubmissionCycle:
    c = SubmissionCycle(
        code="DAILY",
        name="DAILY",
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


def _add_doc_type(db, cycle_id: int) -> DocumentTypeMaster:
    dt = DocumentTypeMaster(
        code="DAILY_DOC",
        name="DAILY_DOC",
        description=None,
        sort_order=0,
        is_active=True,
        default_cycle_id=cycle_id,
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


def _add_req(
    db,
    site_id: int,
    document_type_id: int,
    is_enabled: bool,
    effective_from: date | None,
    effective_to: date | None,
    updated_at: datetime,
) -> DocumentRequirement:
    r = DocumentRequirement(
        site_id=site_id,
        document_type_id=document_type_id,
        is_enabled=is_enabled,
        override_cycle_id=None,
        override_generation_rule=None,
        override_generation_value=None,
        override_due_offset_days=None,
        effective_from=effective_from,
        effective_to=effective_to,
        created_at=updated_at,
        updated_at=updated_at,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_pick_best_disabled_wins_even_if_less_specific(db):
    cycle = _add_cycle(db)
    dt = _add_doc_type(db, cycle.id)

    # 상시 enabled
    r_enabled = _add_req(
        db,
        site_id=1,
        document_type_id=dt.id,
        is_enabled=True,
        effective_from=None,
        effective_to=None,
        updated_at=datetime(2026, 3, 1),
    )
    # 기간 disabled (더 구체)
    r_disabled = _add_req(
        db,
        site_id=1,
        document_type_id=dt.id,
        is_enabled=False,
        effective_from=date(2026, 3, 10),
        effective_to=date(2026, 3, 20),
        updated_at=datetime(2026, 3, 2),
    )

    valid = _list_valid_requirements(db, 1, dt.id, date(2026, 3, 15))
    picked = _pick_best_requirement(valid)
    assert picked.id == r_disabled.id
    assert picked.is_enabled is False
    assert picked.id != r_enabled.id


def test_pick_best_closed_beats_open_and_always(db):
    cycle = _add_cycle(db)
    dt = _add_doc_type(db, cycle.id)

    r_always = _add_req(
        db, 1, dt.id, True, None, None, datetime(2026, 3, 1)
    )
    r_open = _add_req(
        db, 1, dt.id, True, date(2026, 1, 1), None, datetime(2026, 3, 2)
    )
    r_closed = _add_req(
        db, 1, dt.id, True, date(2026, 3, 1), date(2026, 3, 31), datetime(2026, 3, 3)
    )

    valid = _list_valid_requirements(db, 1, dt.id, date(2026, 3, 15))
    picked = _pick_best_requirement(valid)
    assert picked.id == r_closed.id
    assert picked.id != r_open.id
    assert picked.id != r_always.id


def test_pick_best_open_vs_open_tiebreak_updated_at_desc_then_id_desc(db):
    cycle = _add_cycle(db)
    dt = _add_doc_type(db, cycle.id)

    r1 = _add_req(
        db, 1, dt.id, True, date(2026, 1, 1), None, datetime(2026, 3, 1)
    )
    r2 = _add_req(
        db, 1, dt.id, True, None, date(2026, 12, 31), datetime(2026, 3, 2)
    )

    valid = _list_valid_requirements(db, 1, dt.id, date(2026, 3, 15))
    picked = _pick_best_requirement(valid)
    assert picked.id == r2.id
    assert picked.id != r1.id


def test_pick_best_half_open_competition_id_desc_when_updated_at_equal(db):
    cycle = _add_cycle(db)
    dt = _add_doc_type(db, cycle.id)

    # 둘 다 반열린(half-open) 구간이며 updated_at 동일 -> id DESC가 마지막 tie-break로 작동해야 함
    ts = datetime(2026, 3, 5, 10, 0, 0)
    r1 = _add_req(db, 1, dt.id, True, date(2026, 1, 1), None, ts)
    r2 = _add_req(db, 1, dt.id, True, None, date(2026, 12, 31), ts)

    valid = _list_valid_requirements(db, 1, dt.id, date(2026, 3, 15))
    picked = _pick_best_requirement(valid)
    assert picked.id == max(r1.id, r2.id)


def test_pick_best_specificity_beats_updated_at_and_id(db):
    cycle = _add_cycle(db)
    dt = _add_doc_type(db, cycle.id)

    # half-open이 updated_at 최신이어도, closed(닫힌 구간)가 specificity 우선으로 반드시 선택돼야 함
    r_half_open_new = _add_req(
        db, 1, dt.id, True, date(2026, 1, 1), None, datetime(2026, 3, 20)
    )
    r_closed_old = _add_req(
        db, 1, dt.id, True, date(2026, 3, 1), date(2026, 3, 31), datetime(2026, 3, 1)
    )

    valid = _list_valid_requirements(db, 1, dt.id, date(2026, 3, 15))
    picked = _pick_best_requirement(valid)
    assert picked.id == r_closed_old.id
    assert picked.id != r_half_open_new.id

