"""소장·팀장 권한 — 팀원 점수는 팀장만 / 소장은 반려 가능."""

from __future__ import annotations

import base64
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.functional_eval.eval_catalog import build_lowest_grade_scores
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


def _client_for_users(tmp_path: Path, setup_fn) -> tuple[TestClient, TestClient, dict[str, int]]:
    db_file = tmp_path / "fe_mgr_perm.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    from app.modules.functional_eval import models as _fe_models  # noqa: F401
    from app.modules.workers import models as _worker_models  # noqa: F401

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    holder = setup_fn(db)
    db.close()

    def _make_app(user_ns):
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

    mgr_ns = SimpleNamespace(id=1, login_id="alias-mgr", name="Mgr", role=Role.SITE_FUNCTIONAL_EVAL, site_id=1)
    lead_ns = SimpleNamespace(id=2, login_id="alias-lead", name="Lead", role=Role.SITE_FUNCTIONAL_EVAL, site_id=1)
    return _make_app(mgr_ns), _make_app(lead_ns), holder


def _seed_split_site(db, *, worker_count: int = 1) -> dict[str, int]:
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
    batch = FunctionalEvalAttendanceImportBatch(
        period_id=period.id,
        work_date=date(2026, 6, 1),
        original_filename="t.xlsx",
        stored_path="t.xlsx",
    )
    db.add(batch)
    db.flush()
    worker_ids: list[int] = []
    for i in range(worker_count):
        worker = FunctionalEvalWorker(
            period_id=period.id,
            site_code="S01",
            name=f"Worker{i + 1}",
            row_no=i + 1,
            rrn_hash=f"hash{i + 1}",
            assigned_evaluator_login_id="alias-lead",
            is_site_manager=False,
        )
        db.add(worker)
        db.flush()
        worker_ids.append(worker.id)
        db.add(
            FunctionalEvalAttendanceEntry(
                period_id=period.id,
                work_date=date(2026, 6, 1),
                worker_id=worker.id,
                site_code="S01",
                rrn_hash=f"hash{i + 1}",
                name=worker.name,
                batch_id=batch.id,
            )
        )
    period.last_attendance_date = date(2026, 6, 1)
    db.commit()
    return {"worker_id": worker_ids[0]}


def test_manager_cannot_edit_team_worker_scores(tmp_path: Path):
    mgr_client, _, holder = _client_for_users(tmp_path, lambda db: _seed_split_site(db))
    mgr_client.post(
        "/functional-eval/consent/submit",
        json={"signature_data": SIGNATURE_DATA, "consent_acknowledged": True},
    )
    wid = holder["worker_id"]
    scores = build_lowest_grade_scores("FUNCTIONAL")
    res = mgr_client.put(f"/functional-eval/workers/{wid}/assessment/FUNCTIONAL", json={"scores": scores})
    assert res.status_code == 403


def test_manager_reject_team_report_unlocks_leader_scores(tmp_path: Path):
    mgr_client, leader_client, holder = _client_for_users(tmp_path, lambda db: _seed_split_site(db))
    for client in (leader_client, mgr_client):
        client.post(
            "/functional-eval/consent/submit",
            json={"signature_data": SIGNATURE_DATA, "consent_acknowledged": True},
        )
    wid = holder["worker_id"]
    scores = build_lowest_grade_scores("FUNCTIONAL")
    leader_client.put(f"/functional-eval/workers/{wid}/assessment/FUNCTIONAL", json={"scores": scores})
    scores_s = build_lowest_grade_scores("SAFETY")
    leader_client.put(f"/functional-eval/workers/{wid}/assessment/SAFETY", json={"scores": scores_s})
    assert leader_client.post("/functional-eval/my-team/signoff", json={"signature_data": SIGNATURE_DATA}).status_code == 200

    reject = mgr_client.post(
        "/functional-eval/my-site/team-leader/alias-lead/reject-report",
        json={"reject_note": "점수 재검토"},
    )
    assert reject.status_code == 200, reject.text

    retry = leader_client.put(
        f"/functional-eval/workers/{wid}/assessment/FUNCTIONAL",
        json={"scores": scores},
    )
    assert retry.status_code == 200, retry.text
