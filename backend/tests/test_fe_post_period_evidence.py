"""마감 후 포상·제재 이력 제출 및 본사 승인."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.functional_eval import service as fe_service
from app.modules.functional_eval.customer_rewards import REWARD_STATUS_PENDING, submit_customer_reward
from app.modules.functional_eval.sanction_reviews import SANCTION_STATUS_PENDING, list_pending_sanctions
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalWorker
from app.modules.sites.models import Site
from app.modules.users.models import User

_SIGNATURE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture()
def fe_closed_ctx(tmp_path: Path):
    db_file = tmp_path / "fe_post_period.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.functional_eval import models as _fe  # noqa: F401
    from app.modules.users import models as _users  # noqa: F401
    from app.modules.workers import models as _workers  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = Session()
    site = Site(site_code="24018", site_name="테스트")
    db.add(site)
    db.flush()
    user = User(
        id=1,
        name="소장",
        login_id="24018",
        password_hash="x",
        role=Role.SITE_FUNCTIONAL_EVAL,
        ui_type=UIType.SITE,
        site_id=site.id,
    )
    db.add(user)
    period = FunctionalEvalPeriod(
        title="test",
        deadline_date=date.today() - timedelta(days=1),
        is_active=True,
    )
    db.add(period)
    db.flush()
    worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24018",
        row_no=1,
        name="홍길동",
        rrn_hash=hashlib.sha256(b"8804091170112").hexdigest(),
        rrn_masked="880409-1170112",
        is_site_manager=False,
        is_active=True,
    )
    db.add(worker)
    db.commit()
    yield db, user, period, worker
    db.close()


def test_reward_submit_allowed_after_period_close(fe_closed_ctx):
    db, user, period, worker = fe_closed_ctx
    row = submit_customer_reward(
        db,
        period=period,
        user=user,
        worker_id=worker.id,
        photo_path="functional_eval/customer_rewards/1/test.jpg",
        original_filename="test.jpg",
    )
    assert row["status"] == REWARD_STATUS_PENDING


def test_sanction_site_submit_pending_after_period_close(fe_closed_ctx):
    db, user, period, worker = fe_closed_ctx
    result = fe_service.record_sanction(
        db,
        period=period,
        user=user,
        worker_id=worker.id,
        violation_code="INST_TBM",
        evidence_type="COMMENT",
        note="마감 후 제재 신고",
        signature_data=_SIGNATURE,
    )
    assert result["status"] == SANCTION_STATUS_PENDING
    assert any(p["id"] == result["id"] for p in list_pending_sanctions(db, period))


def test_assessment_still_blocked_after_period_close(fe_closed_ctx):
    db, user, period, worker = fe_closed_ctx
    with pytest.raises(ValueError, match="PERIOD_CLOSED"):
        fe_service.save_worker_assessment(db, user, worker.id, "FUNCTIONAL", {"1": "NORMAL"})
