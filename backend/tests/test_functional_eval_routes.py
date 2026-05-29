from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalWorker
from app.modules.functional_eval.routes import router as functional_eval_router
from app.modules.functional_eval.sanctions import resolve_sanction
from app.modules.sites.models import Site
from app.modules.users.models import User


@pytest.mark.parametrize(
    "code,prior,expected_result,expected_strike",
    [
        ("WORK_BELT", 0, "SAME_DAY_EXPULSION", 1),
        ("ACCIDENT_LATE_REPORT", 0, "SITE_PERMANENT_EXPULSION", 1),
        ("INST_TBM", 0, "VERBAL_WARNING", 1),
        ("INST_TBM", 1, "SAFETY_TRAINING_2H", 2),
        ("INST_TBM", 2, "COMPANY_PERMANENT_EXPULSION", 3),
        ("GEN_BASIC_SAFETY", 0, "WARNING", 1),
        ("GEN_BASIC_SAFETY", 1, "SAME_DAY_EXPULSION", 2),
        ("SEVERE_THEFT", 0, "SITE_PERMANENT_BAN", 1),
    ],
)
def test_resolve_sanction_rules(code, prior, expected_result, expected_strike):
    result, strike = resolve_sanction(code, prior)
    assert result == expected_result
    assert strike == expected_strike


def test_functional_eval_sanction_flow(tmp_path: Path):
    db_file = tmp_path / "functional_eval.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="24018", site_name="테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    setup_db.add(
        User(
            id=10,
            name="소장",
            login_id="24018",
            password_hash="x",
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site.id,
            must_change_password=False,
        )
    )
    period = FunctionalEvalPeriod(title="test", deadline_date=date(2026, 12, 31), is_active=True)
    setup_db.add(period)
    setup_db.flush()
    rrn_digits = "8804091170112"
    worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24018",
        row_no=1,
        name="홍길동",
        rrn_hash=hashlib.sha256(rrn_digits.encode()).hexdigest(),
        rrn_masked="880409-1170112",
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add(worker)
    setup_db.commit()
    site_id = site.id
    worker_id = worker.id
    setup_db.close()

    app = FastAPI()
    app.include_router(functional_eval_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    current_user = {
        "value": SimpleNamespace(
            id=10,
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site_id,
            login_id="24018",
        )
    }
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current_user["value"]
    client = TestClient(app)

    catalog_res = client.get("/functional-eval/violation-catalog")
    assert catalog_res.status_code == 200
    assert len(catalog_res.json()["items"]) >= 10

    workers_res = client.get("/functional-eval/my-site/workers")
    assert workers_res.status_code == 200
    assert workers_res.json()["items"][0]["name"] == "홍길동"

    first = client.post(
        "/functional-eval/sanctions",
        json={"worker_id": worker_id, "violation_code": "INST_TBM", "note": "1차"},
    )
    assert first.status_code == 200
    assert first.json()["sanction_result"] == "VERBAL_WARNING"
    assert first.json()["strike_number"] == 1

    second = client.post(
        "/functional-eval/sanctions",
        json={"worker_id": worker_id, "violation_code": "INST_TBM", "note": "2차"},
    )
    assert second.status_code == 200
    assert second.json()["sanction_result"] == "SAFETY_TRAINING_2H"
    assert second.json()["strike_number"] == 2

    immediate = client.post(
        "/functional-eval/sanctions",
        json={"worker_id": worker_id, "violation_code": "WORK_BELT"},
    )
    assert immediate.status_code == 200
    assert immediate.json()["sanction_result"] == "SAME_DAY_EXPULSION"

    history_res = client.get(f"/functional-eval/workers/{worker_id}/history")
    assert history_res.status_code == 200
    body = history_res.json()
    assert body["history_visible"] is True
    assert len(body["sanctions"]) >= 3

    permanent = client.post(
        "/functional-eval/sanctions",
        json={"worker_id": worker_id, "violation_code": "SEVERE_THEFT"},
    )
    assert permanent.status_code == 200
    history2 = client.get(f"/functional-eval/workers/{worker_id}/history")
    assert history2.json()["history_visible"] is False

    mileage_res = client.get(f"/functional-eval/workers/{worker_id}/mileage")
    assert mileage_res.status_code == 200
    assert mileage_res.json()["status"] == "PREPARED"
