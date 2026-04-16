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
from app.modules.safety_features.routes import router as safety_features_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def build_test_client(tmp_path: Path) -> tuple[TestClient, dict[str, SimpleNamespace]]:
    db_file = tmp_path / "test_safety_rows.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.safety_features import models as safety_features_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = testing_session_local()
    site = Site(site_code="S-SAFETY-001", site_name="관리대장 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    setup_db.add_all(
        [
            User(
                id=1,
                name="site-user",
                login_id="site_safety_user",
                password_hash="x",
                site_id=site.id,
                role=Role.SITE,
            ),
            User(
                id=2,
                name="hq-user",
                login_id="hq_safety_user",
                password_hash="x",
                site_id=site.id,
                role=Role.HQ_SAFE,
            ),
        ]
    )
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(safety_features_router)

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


def test_worker_voice_manual_row_management(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)

    create_res = client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "홍길동",
            "opinion_kind": "대면청취",
            "opinion_text": "안전모 끈 개선 요청",
            "action_before": "턱끈 풀림",
            "action_after": "신규 제품 지급",
            "action_status": "DONE",
            "action_owner": "안전팀",
        },
    )
    assert create_res.status_code == 200

    ledger_res = client.get("/safety-features/worker-voice/ledger")
    assert ledger_res.status_code == 200
    payload = ledger_res.json()
    assert payload["ledger"]["source_type"] == "MANUAL"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["worker_name"] == "홍길동"
    assert payload["items"][0]["action_after"] == "신규 제품 지급"

    update_res = client.post(
        f"/safety-features/worker-voice/items/{payload['items'][0]['id']}",
        data={
            "worker_name": "홍길동",
            "worker_birth_date": "",
            "worker_phone_number": "",
            "opinion_kind": "대면청취",
            "opinion_text": "안전모 끈 개선 요청",
            "action_before": "턱끈 풀림",
            "action_after": "전량 교체",
            "action_status": "DONE",
            "action_owner": "안전팀",
        },
    )
    assert update_res.status_code == 200

    ledger_res = client.get("/safety-features/worker-voice/ledger")
    assert ledger_res.json()["items"][0]["action_after"] == "전량 교체"

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    list_res = client.get("/safety-features/worker-voice/items")
    assert list_res.status_code == 200
    assert list_res.json()["items"][0]["ledger_source_type"] == "MANUAL"


def test_nonconformity_manual_row_management(tmp_path: Path):
    client, _ = build_test_client(tmp_path)

    create_res = client.post(
        "/safety-features/nonconformities/items",
        data={
            "issue_text": "난간 고정 불량",
            "action_before": "임시 고정 상태",
            "action_after": "재시공 완료",
            "action_status": "IN_PROGRESS",
            "action_due_date": "2026-04-12",
            "completed_at": "",
            "action_owner": "시공팀",
        },
    )
    assert create_res.status_code == 200

    current_res = client.get("/safety-features/nonconformities/overview/current")
    assert current_res.status_code == 200
    payload = current_res.json()
    assert payload["ledger"]["source_type"] == "MANUAL"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["issue_text"] == "난간 고정 불량"
    assert payload["items"][0]["action_status"] == "in_progress"

    item_id = payload["items"][0]["id"]
    update_res = client.post(
        f"/safety-features/nonconformities/items/{item_id}",
        data={
            "issue_text": "난간 고정 불량",
            "action_before": "임시 고정 상태",
            "action_after": "재시공 완료",
            "action_status": "DONE",
            "action_due_date": "2026-04-12",
            "completed_at": "2026-04-12",
            "action_owner": "시공팀",
        },
    )
    assert update_res.status_code == 200

    current_res = client.get("/safety-features/nonconformities/overview/current")
    assert current_res.json()["items"][0]["action_status"] == "completed"


def test_worker_voice_hq_final_requires_site_approval(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)
    create_res = client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "홍길동",
            "opinion_kind": "대면청취",
            "opinion_text": "의견",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    )
    assert create_res.status_code == 200
    item_id = client.get("/safety-features/worker-voice/ledger").json()["items"][0]["id"]
    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/approve-risk-db-registration").status_code == 409


def test_worker_voice_site_reject_blocks_hq_final(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)
    client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "홍길동",
            "opinion_kind": "대면청취",
            "opinion_text": "의견",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    )
    item_id = client.get("/safety-features/worker-voice/ledger").json()["items"][0]["id"]
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/site-reject", data={"reject_note": "보완"}).status_code == 200
    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/approve-risk-db-registration").status_code == 409


def test_worker_voice_hq_approve_requires_db_request(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)
    client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "a",
            "opinion_kind": "x",
            "opinion_text": "y",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    )
    item_id = client.get("/safety-features/worker-voice/ledger").json()["items"][0]["id"]
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/site-approve").status_code == 200
    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/approve-risk-db-registration").status_code == 409


def test_nonconformity_hq_final_requires_site_approval(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)
    client.post(
        "/safety-features/nonconformities/items",
        data={
            "issue_text": "테스트",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_due_date": "",
            "completed_at": "",
            "action_owner": "",
        },
    )
    item_id = client.get("/safety-features/nonconformities/overview/current").json()["items"][0]["id"]
    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    assert client.post(f"/safety-features/nonconformities/items/{item_id}/approve-risk-db-registration").status_code == 409


def test_nonconformity_approval_chain(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)
    client.post(
        "/safety-features/nonconformities/items",
        data={
            "issue_text": "체인 테스트",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_due_date": "",
            "completed_at": "",
            "action_owner": "",
        },
    )
    item_id = client.get("/safety-features/nonconformities/overview/current").json()["items"][0]["id"]
    assert client.post(f"/safety-features/nonconformities/items/{item_id}/site-approve").status_code == 200
    assert client.post(f"/safety-features/nonconformities/items/{item_id}/request-risk-db-registration").status_code == 200
    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    assert client.post(f"/safety-features/nonconformities/items/{item_id}/approve-risk-db-registration").status_code == 200
    assert client.post(f"/safety-features/nonconformities/items/{item_id}/reward-candidate").status_code == 200
    row = next(r for r in client.get("/safety-features/nonconformities/items").json()["items"] if r["id"] == item_id)
    assert row["site_approved"] is True
    assert row["hq_checked"] is True
    assert row["reward_candidate"] is True
    assert row["ready_for_risk_db"] is True


def test_hq_reject_risk_db_then_not_ready(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)
    client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "a",
            "opinion_kind": "x",
            "opinion_text": "z",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    )
    item_id = client.get("/safety-features/worker-voice/ledger").json()["items"][0]["id"]
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/site-approve").status_code == 200
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/request-risk-db-registration").status_code == 200
    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/reject-risk-db-registration", data={"reject_note": "no"}).status_code == 200
    row = next(r for r in client.get("/safety-features/worker-voice/items").json()["items"] if r["id"] == item_id)
    assert row["ready_for_risk_db"] is False
    assert row["risk_db_hq_status"] == "rejected"


def test_site_cannot_call_hq_risk_approve(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)
    client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "a",
            "opinion_kind": "x",
            "opinion_text": "w",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    )
    item_id = client.get("/safety-features/worker-voice/ledger").json()["items"][0]["id"]
    client.post(f"/safety-features/worker-voice/items/{item_id}/site-approve")
    client.post(f"/safety-features/worker-voice/items/{item_id}/request-risk-db-registration")
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/approve-risk-db-registration").status_code == 403


def test_hq_cannot_call_site_accept(tmp_path: Path):
    client, current_user = build_test_client(tmp_path)
    client.post(
        "/safety-features/worker-voice/items",
        data={
            "worker_name": "a",
            "opinion_kind": "x",
            "opinion_text": "w",
            "action_before": "",
            "action_after": "",
            "action_status": "",
            "action_owner": "",
        },
    )
    item_id = client.get("/safety-features/worker-voice/ledger").json()["items"][0]["id"]
    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=1)
    assert client.post(f"/safety-features/worker-voice/items/{item_id}/site-approve").status_code == 403


def test_risk_db_gate_helpers():
    from app.modules.safety_features import risk_gates as rg
    from app.modules.safety_features.risk_gates import nonconformity_item_ready_for_risk_db, worker_voice_item_ready_for_risk_db

    base = SimpleNamespace(
        site_rejected=False,
        site_approved=True,
        receipt_decision=rg.RECEIPT_ACCEPTED,
        risk_db_request_status=rg.RISK_DB_REQ_PENDING,
        risk_db_hq_status=rg.RISK_DB_HQ_PENDING,
        hq_checked=False,
    )
    assert worker_voice_item_ready_for_risk_db(base) is False
    requested = SimpleNamespace(
        site_rejected=False,
        site_approved=True,
        receipt_decision=rg.RECEIPT_ACCEPTED,
        risk_db_request_status=rg.RISK_DB_REQ_REQUESTED,
        risk_db_hq_status=rg.RISK_DB_HQ_PENDING,
        hq_checked=False,
    )
    assert worker_voice_item_ready_for_risk_db(requested) is False
    ready = SimpleNamespace(
        site_rejected=False,
        site_approved=True,
        receipt_decision=rg.RECEIPT_ACCEPTED,
        risk_db_request_status=rg.RISK_DB_REQ_REQUESTED,
        risk_db_hq_status=rg.RISK_DB_HQ_APPROVED,
        hq_checked=True,
    )
    assert worker_voice_item_ready_for_risk_db(ready) is True
    rejected = SimpleNamespace(
        site_rejected=True,
        site_approved=False,
        receipt_decision=rg.RECEIPT_ACCEPTED,
        risk_db_request_status=rg.RISK_DB_REQ_REQUESTED,
        risk_db_hq_status=rg.RISK_DB_HQ_APPROVED,
        hq_checked=True,
    )
    assert worker_voice_item_ready_for_risk_db(rejected) is False
    assert nonconformity_item_ready_for_risk_db(ready) is True
