from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.dashboard.routes import router as dashboard_router
from app.modules.dashboard.risk_db_overview import compute_risk_db_overview
from app.modules.safety_features import risk_gates as rg
from app.modules.safety_features.models import WorkerVoiceItem, WorkerVoiceLedger
from app.modules.safety_features.routes import router as safety_features_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def _app_with_routers(tmp_path: Path) -> tuple[TestClient, dict]:
    db_file = tmp_path / "dash_risk.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.safety_features import models as safety_features_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup = testing_session_local()
    site = Site(site_code="S-DASH-RISK", site_name="대시보드 집계 현장")
    setup.add(site)
    setup.flush()
    setup.add_all(
        [
            User(
                id=1,
                name="site-u",
                login_id="site_dash_risk",
                password_hash="x",
                site_id=site.id,
                role=Role.SITE,
            ),
            User(
                id=2,
                name="hq-u",
                login_id="hq_dash_risk",
                password_hash="x",
                site_id=site.id,
                role=Role.HQ_SAFE,
            ),
        ],
    )
    setup.commit()
    setup.close()

    app = FastAPI()
    app.include_router(safety_features_router)
    app.include_router(dashboard_router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    current_user = {"value": SimpleNamespace(id=1, role=Role.SITE, site_id=1)}
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current_user["value"]
    return TestClient(app), current_user


def test_risk_db_overview_forbidden_nonledger_role(tmp_path: Path):
    client, current_user = _app_with_routers(tmp_path)
    current_user["value"] = SimpleNamespace(id=9, role=Role.HQ_OTHER, site_id=None)
    assert client.get("/dashboard/risk-db-overview").status_code == 403


def test_risk_db_overview_site_db_request_needed_and_requested(tmp_path: Path):
    client, current_user = _app_with_routers(tmp_path)
    assert client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "a",
            "opinion_kind": "x",
            "opinion_text": "needs db req",
            "action_before": "",
            "action_after": "",
            "action_status": "in_progress",
            "action_owner": "",
        },
    ).status_code == 200
    assert client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "b",
            "opinion_kind": "x",
            "opinion_text": "requested",
            "action_before": "",
            "action_after": "",
            "action_status": "completed",
            "action_owner": "",
        },
    ).status_code == 200
    ledger = client.get("/safety-features/worker-voice/ledger").json()
    ids = [it["id"] for it in ledger["items"]]
    assert len(ids) >= 2
    for iid in ids:
        assert client.post(f"/safety-features/worker-voice/items/{iid}/site-approve").status_code == 200
    assert client.post(f"/safety-features/worker-voice/items/{ids[1]}/request-risk-db-registration").status_code == 200

    ov = client.get("/dashboard/risk-db-overview").json()
    assert ov["site"]["combined"]["db_requested"] == 1
    assert ov["site"]["worker_voice"]["db_requested"] == 1
    assert ov["site"]["nonconformity"]["db_requested"] == 0
    assert ov["site"]["combined"]["db_request_needed"] == 1
    assert ov["site"]["combined"]["in_progress"] == 1
    assert ov["site"]["combined"]["action_completed"] == 1


def test_risk_db_overview_hq_pending_approval_and_rejected(tmp_path: Path):
    client, current_user = _app_with_routers(tmp_path)
    assert client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "hq1",
            "opinion_kind": "x",
            "opinion_text": "pending hq",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    ).status_code == 200
    item_id = client.get("/safety-features/worker-voice/ledger").json()["items"][0]["id"]
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/site-approve").status_code == 200
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/request-risk-db-registration").status_code == 200

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    ov1 = client.get("/dashboard/risk-db-overview").json()
    assert ov1["hq"]["combined"]["pending_requests"] >= 1
    assert ov1["hq"]["combined"]["pending_approval"] >= 1
    assert ov1["hq"]["worker_voice"]["pending_approval"] >= 1

    assert client.post(f"/safety-features/worker-voice/items/{item_id}/reject-risk-db-registration", data={"reject_note": "x"}).status_code == 200
    ov2 = client.get("/dashboard/risk-db-overview").json()
    assert ov2["hq"]["combined"]["rejected"] >= 1
    assert ov2["hq"]["combined"]["pending_approval"] < ov1["hq"]["combined"]["pending_approval"]


def test_risk_db_overview_approved_matches_ready_for_risk_db(tmp_path: Path):
    client, current_user = _app_with_routers(tmp_path)
    current_user["value"] = SimpleNamespace(id=1, role=Role.SITE, site_id=1)
    assert client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "ready",
            "opinion_kind": "x",
            "opinion_text": "full chain",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    ).status_code == 200
    item_id = client.get("/safety-features/worker-voice/ledger").json()["items"][0]["id"]
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/site-approve").status_code == 200
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/request-risk-db-registration").status_code == 200
    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/approve-risk-db-registration").status_code == 200

    ov = client.get("/dashboard/risk-db-overview").json()
    wv = client.get("/safety-features/worker-voice/items").json()["items"]
    nc = client.get("/safety-features/nonconformities/items").json().get("items", [])
    row = next(r for r in wv if r["id"] == item_id)
    assert row["ready_for_risk_db"] is True
    expected_ready = sum(1 for r in wv + nc if r.get("ready_for_risk_db"))
    assert ov["hq"]["combined"]["approved"] == expected_ready
    assert ov["hq"]["worker_voice"]["approved"] == sum(1 for r in wv if r.get("ready_for_risk_db"))


def test_orphan_hq_approve_without_request_not_counted_approved(tmp_path: Path):
    """DB에만 비정상(요청 없이 HQ승인)으로 넣어도 집계 approved에 포함되지 않아야 함."""
    db_file = tmp_path / "dash_orphan.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.safety_features import models as safety_features_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = Session()
    site = Site(site_code="ORPH", site_name="orph")
    db.add(site)
    db.flush()
    db.add(
        User(
            id=1,
            name="u",
            login_id="orph_u",
            password_hash="x",
            site_id=site.id,
            role=Role.SITE,
        )
    )
    db.flush()
    led = WorkerVoiceLedger(
        site_id=site.id,
        title="L",
        file_path="",
        file_name="",
        file_size=0,
        uploaded_by_user_id=1,
        source_type="MANUAL",
    )
    db.add(led)
    db.flush()
    bad = WorkerVoiceItem(
        ledger_id=led.id,
        row_no=1,
        opinion_text="x",
        receipt_decision=rg.RECEIPT_ACCEPTED,
        site_approved=True,
        site_rejected=False,
        risk_db_request_status=rg.RISK_DB_REQ_PENDING,
        risk_db_hq_status=rg.RISK_DB_HQ_APPROVED,
        hq_checked=True,
    )
    db.add(bad)
    db.commit()
    overview = compute_risk_db_overview(db, site.id)
    db.close()
    assert overview["hq"]["combined"]["approved"] == 0
    assert overview["hq"]["worker_voice"]["approved"] == 0


def test_combined_hq_equals_worker_voice_plus_nonconformity(tmp_path: Path):
    client, _current_user = _app_with_routers(tmp_path)
    assert client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "wv",
            "opinion_kind": "x",
            "opinion_text": "one",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    ).status_code == 200
    assert client.post(
        "/safety-features/nonconformities/items",
        data={
            "issue_text": "nc one",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_due_date": "",
            "completed_at": "",
            "action_owner": "",
        },
    ).status_code == 200
    ov = client.get("/dashboard/risk-db-overview").json()
    for key in ("pending_requests", "pending_approval", "rejected", "approved", "reward_candidates"):
        c = ov["hq"]["combined"][key]
        assert c == ov["hq"]["worker_voice"][key] + ov["hq"]["nonconformity"][key], key
    for key in ("unreceived", "in_progress", "action_completed", "db_request_needed", "db_requested"):
        c = ov["site"]["combined"][key]
        assert c == ov["site"]["worker_voice"][key] + ov["site"]["nonconformity"][key], key
