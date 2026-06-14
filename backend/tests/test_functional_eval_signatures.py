"""기능인제 서명·동의 테스트."""

from __future__ import annotations

import base64
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
from app.modules.functional_eval.models import (
    FunctionalEvalAttendanceEntry,
    FunctionalEvalAttendanceImportBatch,
    FunctionalEvalPeriod,
    FunctionalEvalSiteRegistry,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.routes import router as functional_eval_router
from app.modules.sites.models import Site
from app.modules.users.models import User

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
SIGNATURE_DATA = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode("ascii")


def _client_for_user(tmp_path: Path, user_ns: SimpleNamespace, setup_fn) -> TestClient:
    db_file = tmp_path / "fe_sign.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    from app.modules.functional_eval import models as _fe_models  # noqa: F401
    from app.modules.workers import models as _worker_models  # noqa: F401

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    setup_fn(db)
    db.close()

    app = FastAPI()
    app.include_router(functional_eval_router)

    def _db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: user_ns
    return TestClient(app)


def test_consent_submit_once(tmp_path: Path):
    user_ns = SimpleNamespace(id=1, login_id="alias-mgr", name="Mgr", role=Role.SITE_FUNCTIONAL_EVAL)

    def setup(db):
        site = Site(site_code="S01", site_name="Test")
        db.add(site)
        db.add(
            User(
                id=1,
                login_id="alias-mgr",
                name="Mgr",
                role=Role.SITE_FUNCTIONAL_EVAL,
                ui_type=UIType.SITE,
                site_id=1,
                password_hash="x",
                must_change_password=False,
            )
        )
        db.commit()

    client = _client_for_user(tmp_path, user_ns, setup)
    assert client.get("/functional-eval/consent/status").json()["required"] is True
    res = client.post(
        "/functional-eval/consent/submit",
        json={"signature_data": SIGNATURE_DATA, "consent_acknowledged": True},
    )
    assert res.status_code == 200, res.text
    assert client.get("/functional-eval/consent/status").json()["required"] is False
    assert client.post(
        "/functional-eval/consent/submit",
        json={"signature_data": SIGNATURE_DATA, "consent_acknowledged": True},
    ).status_code == 409


def test_signature_lock_after_team_signoff(tmp_path: Path):
    worker_holder: dict[str, int] = {}

    def setup(db):
        site = Site(site_code="S01", site_name="Test")
        db.add(site)
        db.flush()
        db.add(
            User(
                id=1,
                login_id="alias-mgr",
                name="Mgr",
                role=Role.SITE_FUNCTIONAL_EVAL,
                ui_type=UIType.SITE,
                site_id=site.id,
                password_hash="x",
                must_change_password=False,
            )
        )
        db.add(
            User(
                id=2,
                login_id="alias-lead",
                name="Lead",
                role=Role.SITE_FUNCTIONAL_EVAL,
                ui_type=UIType.SITE,
                site_id=site.id,
                password_hash="x",
                must_change_password=False,
            )
        )
        period = FunctionalEvalPeriod(title="test", deadline_date=date(2026, 12, 31), is_active=True)
        db.add(period)
        db.flush()
        db.add(
            FunctionalEvalSiteRegistry(
                site_code="S01",
                erp_site_label="Test",
                site_alias="alias",
                manager_name="Mgr",
                manager_login_id="alias-mgr",
            )
        )
        worker = FunctionalEvalWorker(
            period_id=period.id,
            site_code="S01",
            name="Worker1",
            row_no=1,
            rrn_hash="hash1",
            assigned_evaluator_login_id="alias-lead",
            is_site_manager=False,
        )
        db.add(worker)
        db.flush()
        batch = FunctionalEvalAttendanceImportBatch(
            period_id=period.id,
            work_date=date(2026, 6, 1),
            original_filename="t.xlsx",
            stored_path="t.xlsx",
        )
        db.add(batch)
        db.flush()
        db.add(
            FunctionalEvalAttendanceEntry(
                period_id=period.id,
                work_date=date(2026, 6, 1),
                worker_id=worker.id,
                site_code="S01",
                rrn_hash="hash1",
                name="Worker1",
                batch_id=batch.id,
            )
        )
        period.last_attendance_date = date(2026, 6, 1)
        worker_holder["id"] = worker.id
        db.commit()

    leader_ns = SimpleNamespace(
        id=2, login_id="alias-lead", name="Lead", role=Role.SITE_FUNCTIONAL_EVAL, site_id=1
    )
    client = _client_for_user(tmp_path, leader_ns, setup)
    client.post(
        "/functional-eval/consent/submit",
        json={"signature_data": SIGNATURE_DATA, "consent_acknowledged": True},
    )

    from app.modules.functional_eval.eval_catalog import build_lowest_grade_scores

    wid = worker_holder["id"]
    scores = build_lowest_grade_scores("FUNCTIONAL")
    client.put(f"/functional-eval/workers/{wid}/assessment/FUNCTIONAL", json={"scores": scores})
    scores_s = build_lowest_grade_scores("SAFETY")
    client.put(f"/functional-eval/workers/{wid}/assessment/SAFETY", json={"scores": scores_s})

    sign = client.post("/functional-eval/my-team/signoff", json={"signature_data": SIGNATURE_DATA})
    assert sign.status_code == 200, sign.text

    retry = client.put(
        f"/functional-eval/workers/{wid}/assessment/FUNCTIONAL",
        json={"scores": scores},
    )
    assert retry.status_code == 409
