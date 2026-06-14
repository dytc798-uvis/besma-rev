from __future__ import annotations

import base64
import hashlib
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from unittest.mock import patch

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
from app.modules.functional_eval.sanctions import resolve_sanction
from app.modules.sites.models import Site
from app.modules.users.models import User

_TEST_SIGNATURE_DATA = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _post_sanction(
    client: TestClient,
    *,
    worker_id: int,
    violation_code: str,
    note: str = "테스트 제재 근거",
    evidence_type: str = "COMMENT",
):
    return client.post(
        "/functional-eval/sanctions",
        data={
            "worker_id": str(worker_id),
            "violation_code": violation_code,
            "evidence_type": evidence_type,
            "note": note,
            "signature_data": _TEST_SIGNATURE_DATA,
        },
    )


def _save_safety_with_issues(client: TestClient, worker_id: int):
    from app.modules.functional_eval.eval_catalog import build_lowest_grade_scores

    return client.put(
        f"/functional-eval/workers/{worker_id}/assessment/SAFETY",
        json={"scores": build_lowest_grade_scores("SAFETY")},
    )


def _save_safety_with_single_bottom(client: TestClient, worker_id: int, criterion_id: str = "c2"):
    from app.modules.functional_eval.eval_catalog import build_top_grade_scores

    scores = build_top_grade_scores("SAFETY")
    scores[criterion_id] = "BOTTOM"
    return client.put(
        f"/functional-eval/workers/{worker_id}/assessment/SAFETY",
        json={"scores": scores},
    )


def _seed_attendance(db, period: FunctionalEvalPeriod, worker: FunctionalEvalWorker, work_date: date | None = None):
    wd = work_date or date(2026, 5, 29)
    batch = FunctionalEvalAttendanceImportBatch(
        period_id=period.id,
        work_date=wd,
        original_filename="test.xlsx",
        stored_path="storage/test.xlsx",
        total_rows=1,
        linked_workers=1,
    )
    db.add(batch)
    db.flush()
    db.add(
        FunctionalEvalAttendanceEntry(
            period_id=period.id,
            work_date=wd,
            worker_id=worker.id,
            site_code=worker.site_code,
            rrn_hash=worker.rrn_hash,
            name=worker.name,
            batch_id=batch.id,
        )
    )
    period.last_attendance_date = wd
    db.add(period)
    db.commit()


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
    setup_db.flush()
    _seed_attendance(setup_db, period, worker)
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
    workers_body = workers_res.json()
    assert workers_body["items"][0]["name"] == "홍길동"
    assert workers_body["evaluator"]["role"] == "MANAGER"

    safety_res = _save_safety_with_issues(client, worker_id)
    assert safety_res.status_code == 200

    first = _post_sanction(client, worker_id=worker_id, violation_code="INST_TBM", note="1차")
    assert first.status_code == 200
    assert first.json()["sanction_result"] == "VERBAL_WARNING"
    assert first.json()["strike_number"] == 1
    assert first.json()["penalty_points"] == 0

    second = _post_sanction(client, worker_id=worker_id, violation_code="INST_TBM", note="2차")
    assert second.status_code == 200
    assert second.json()["sanction_result"] == "SAFETY_TRAINING_2H"
    assert second.json()["strike_number"] == 2
    assert second.json()["penalty_points"] == 5

    immediate = _post_sanction(client, worker_id=worker_id, violation_code="WORK_BELT", note="안전벨트 미착용")
    assert immediate.status_code == 200
    assert immediate.json()["sanction_result"] == "SAME_DAY_EXPULSION"

    history_res = client.get(f"/functional-eval/workers/{worker_id}/history")
    assert history_res.status_code == 200
    body = history_res.json()
    assert body["history_visible"] is True
    assert len(body["sanctions"]) >= 3

    permanent = _post_sanction(client, worker_id=worker_id, violation_code="SEVERE_THEFT", note="절도 적발")
    assert permanent.status_code == 200
    history2 = client.get(f"/functional-eval/workers/{worker_id}/history")
    assert history2.json()["history_visible"] is False

    mileage_res = client.get(f"/functional-eval/workers/{worker_id}/mileage")
    assert mileage_res.status_code == 200
    mileage = mileage_res.json()
    assert mileage["status"] == "PENALTY"
    assert mileage["points"] == -5
    assert mileage["penalty_points"] == 5


def test_sanction_register_without_safety_bottom(tmp_path: Path):
    db_file = tmp_path / "sanction_no_bottom.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.functional_eval.eval_catalog import build_top_grade_scores
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
    worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24018",
        row_no=1,
        name="직영근로",
        rrn_hash=hashlib.sha256(b"8804091170113").hexdigest(),
        rrn_masked="880409-1170113",
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add(worker)
    setup_db.flush()
    _seed_attendance(setup_db, period, worker)
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=10,
        role=Role.SITE_FUNCTIONAL_EVAL,
        ui_type=UIType.SITE,
        site_id=site_id,
        login_id="24018",
    )
    client = TestClient(app)

    res = _post_sanction(client, worker_id=worker_id, violation_code="INST_QR_ACTIVITY", note="평가 전 제재")
    assert res.status_code == 200
    assert res.json()["penalty_points"] == 0

    top_only = client.put(
        f"/functional-eval/workers/{worker_id}/assessment/SAFETY",
        json={"scores": build_top_grade_scores("SAFETY")},
    )
    assert top_only.status_code == 200
    assert top_only.json()["assessment"]["grade_code"] == "S"

    sanction = _post_sanction(client, worker_id=worker_id, violation_code="INST_TBM", note="TBM 미참여")
    assert sanction.status_code == 200
    assert sanction.json()["penalty_points"] == 0

    safety = client.get(f"/functional-eval/workers/{worker_id}/assessment/SAFETY").json()["assessment"]
    assert safety["scores"]["c1"] == "BOTTOM"
    assert safety["total_score"] < safety["max_score"]

    repeat = _post_sanction(client, worker_id=worker_id, violation_code="INST_TBM", note="TBM 재발")
    assert repeat.status_code == 200
    assert repeat.json()["penalty_points"] == 5

    adjusted = client.get(f"/functional-eval/workers/{worker_id}/assessment/SAFETY").json()["assessment"]
    assert adjusted["adjustment_penalty"] == 5
    assert adjusted["total_score"] == adjusted["base_total_score"] - 5


def test_functional_eval_assessment_flow(tmp_path: Path):
    """2-1 기능 인사고과: catalog → 저장 → 목록 반영 (평가가 핵심)."""
    db_file = tmp_path / "functional_eval_assess.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.functional_eval.eval_catalog import get_criteria
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="26025", site_name="테스트")
    setup_db.add(site)
    setup_db.flush()
    setup_db.add(
        User(
            id=11,
            name="강현석",
            login_id="26025",
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
    worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="26025",
        row_no=1,
        name="김테스트",
        rrn_hash=hashlib.sha256(b"9001011234567").hexdigest(),
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add(worker)
    setup_db.flush()
    _seed_attendance(setup_db, period, worker)
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
            id=11,
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site_id,
            login_id="26025",
        )
    }
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current_user["value"]
    client = TestClient(app)

    catalog_res = client.get("/functional-eval/eval-catalog")
    assert catalog_res.status_code == 200
    body = catalog_res.json()
    assert len(body["FUNCTIONAL"]["criteria"]) >= 5
    assert len(body["SAFETY"]["criteria"]) >= 3

    criteria = get_criteria("FUNCTIONAL")
    scores = {c["id"]: c["grades"][0]["key"] for c in criteria}

    get_empty = client.get(f"/functional-eval/workers/{worker_id}/assessment/FUNCTIONAL")
    assert get_empty.status_code == 200
    assert get_empty.json()["assessment"] is None

    save_res = client.put(
        f"/functional-eval/workers/{worker_id}/assessment/FUNCTIONAL",
        json={"scores": scores},
    )
    assert save_res.status_code == 200
    saved = save_res.json()["assessment"]
    assert saved["is_complete"] is True
    assert saved["total_score"] > 0
    assert saved["grade_code"] in {"S", "A", "B", "C"}

    workers_res = client.get("/functional-eval/my-site/workers")
    assert workers_res.status_code == 200
    item = workers_res.json()["items"][0]
    assert item["functional_assessment"]["is_complete"] is True
    assert item["row_no"] == 1

    incomplete = client.put(
        f"/functional-eval/workers/{worker_id}/assessment/FUNCTIONAL",
        json={"scores": {criteria[0]["id"]: criteria[0]["grades"][0]["key"]}},
    )
    assert incomplete.status_code == 400


def test_hq_eval_summary(tmp_path: Path):
    """본사 HQ: 평가 등급 표·현장별 진행 집계."""
    db_file = tmp_path / "functional_eval_hq.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.functional_eval.eval_catalog import get_criteria
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="26025", site_name="청라현장")
    setup_db.add(site)
    setup_db.flush()
    setup_db.add(
        User(
            id=20,
            name="본사",
            login_id="hq1",
            password_hash="x",
            role=Role.HQ_SAFE,
            ui_type=UIType.HQ_SAFE,
            must_change_password=False,
        )
    )
    setup_db.add(
        User(
            id=21,
            name="소장",
            login_id="26025",
            password_hash="x",
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site.id,
            must_change_password=False,
        )
    )
    period = FunctionalEvalPeriod(title="test", deadline_date=date(2026, 6, 26), is_active=True)
    setup_db.add(period)
    setup_db.flush()
    worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="26025",
        site_name="청라현장",
        row_no=2,
        name="이근로",
        rrn_hash=hashlib.sha256(b"9001011234567").hexdigest(),
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add(worker)
    setup_db.flush()
    _seed_attendance(setup_db, period, worker)
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

    hq_user = SimpleNamespace(id=20, role=Role.HQ_SAFE, ui_type=UIType.HQ_SAFE, site_id=None, login_id="hq1")
    site_user = SimpleNamespace(id=21, role=Role.SITE_FUNCTIONAL_EVAL, ui_type=UIType.SITE, site_id=site_id, login_id="26025")

    app.dependency_overrides[get_db] = override_get_db

    # 소장이 기능 평가 저장
    app.dependency_overrides[get_current_user_with_bypass] = lambda: site_user
    site_client = TestClient(app)
    criteria = get_criteria("FUNCTIONAL")
    scores = {c["id"]: c["grades"][0]["key"] for c in criteria}
    assert site_client.put(
        f"/functional-eval/workers/{worker_id}/assessment/FUNCTIONAL",
        json={"scores": scores},
    ).status_code == 200

    safety_criteria = get_criteria("SAFETY")
    safety_scores = {c["id"]: c["grades"][0]["key"] for c in safety_criteria}
    assert site_client.put(
        f"/functional-eval/workers/{worker_id}/assessment/SAFETY",
        json={"scores": safety_scores},
    ).status_code == 200

    app.dependency_overrides[get_current_user_with_bypass] = lambda: hq_user
    hq_client = TestClient(app)

    overview = hq_client.get("/functional-eval/hq/summary")
    assert overview.status_code == 200
    ob = overview.json()
    assert ob["totals"]["workers"] == 1
    assert ob["totals"]["fully_complete"] == 1
    assert len(ob["sites"]) == 1
    assert ob["sites"][0]["progress"] == "1/1"
    assert ob["sites"][0]["evaluator_name"] == "소장"

    detail2 = hq_client.get("/functional-eval/hq/sites/26025/evaluations")
    assert len(detail2.json()["eval_rows"]) == 1
    row = detail2.json()["eval_rows"][0]
    assert row["name"] == "이근로"
    assert row["functional_grade"] != "미평가"
    assert row["safety_grade"] != "미평가"

    export_res = hq_client.get("/functional-eval/hq/export/evaluations")
    assert export_res.status_code == 200
    assert "spreadsheetml" in export_res.headers.get("content-type", "")


def test_team_leader_evaluator_session_and_filter(tmp_path: Path):
    db_file = tmp_path / "fe_team_leader.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.functional_eval.models import FunctionalEvalSiteRegistry
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="24025", site_name="대우청라")
    setup_db.add(site)
    setup_db.flush()
    setup_db.add(
        FunctionalEvalSiteRegistry(
            site_code="24025",
            site_alias="대우청라",
            manager_name="박명식",
            manager_login_id="대우청라-박명식",
            erp_site_label="청라C18",
        )
    )
    setup_db.add(
        User(
            id=30,
            name="박명식",
            login_id="대우청라-박명식",
            password_hash="x",
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site.id,
        )
    )
    setup_db.add(
        User(
            id=31,
            name="김팀장",
            login_id="대우청라-김팀장",
            password_hash="x",
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site.id,
        )
    )
    period = FunctionalEvalPeriod(title="test", deadline_date=date(2026, 12, 31), is_active=True)
    setup_db.add(period)
    setup_db.flush()
    w1 = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24025",
        row_no=1,
        name="근로자A",
        rrn_hash=hashlib.sha256(b"a").hexdigest(),
        assigned_evaluator_login_id="대우청라-김팀장",
        is_site_manager=False,
        is_active=True,
    )
    w2 = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24025",
        row_no=2,
        name="근로자B",
        rrn_hash=hashlib.sha256(b"b").hexdigest(),
        assigned_evaluator_login_id="대우청라-박명식",
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add_all([w1, w2])
    setup_db.flush()
    _seed_attendance(setup_db, period, w1)
    _seed_attendance(setup_db, period, w2, work_date=date(2026, 5, 29))
    site_id = site.id
    setup_db.close()

    app = FastAPI()
    app.include_router(functional_eval_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    split_patch = patch("app.modules.functional_eval.service.TEAM_LEADER_SPLIT_THRESHOLD", 1)

    manager = SimpleNamespace(
        id=30,
        role=Role.SITE_FUNCTIONAL_EVAL,
        ui_type=UIType.SITE,
        site_id=site_id,
        login_id="대우청라-박명식",
        name="박명식",
    )
    leader = SimpleNamespace(
        id=31,
        role=Role.SITE_FUNCTIONAL_EVAL,
        ui_type=UIType.SITE,
        site_id=site_id,
        login_id="대우청라-김팀장",
        name="김팀장",
    )
    hq = SimpleNamespace(id=40, role=Role.HQ_SAFE, ui_type=UIType.HQ_SAFE, site_id=None, login_id="hq1")

    with split_patch:
        app.dependency_overrides[get_current_user_with_bypass] = lambda: manager
        manager_client = TestClient(app)
        manager_res = manager_client.get("/functional-eval/my-site/workers")
        assert manager_res.status_code == 200
        manager_body = manager_res.json()
        assert manager_body["evaluator"]["role"] == "MANAGER"
        assert len(manager_body["items"]) == 1
        assert manager_body["items"][0]["name"] == "근로자B"

        app.dependency_overrides[get_current_user_with_bypass] = lambda: leader
        leader_client = TestClient(app)
        leader_res = leader_client.get("/functional-eval/my-site/workers")
        assert leader_res.status_code == 200
        leader_body = leader_res.json()
        assert leader_body["evaluator"]["role"] == "TEAM_LEADER"
        assert leader_body["evaluator"]["assigned_worker_count"] == 1
        assert [w["name"] for w in leader_body["items"]] == ["근로자A"]

        app.dependency_overrides[get_current_user_with_bypass] = lambda: hq
        hq_client = TestClient(app)
        accounts = hq_client.get("/functional-eval/hq/evaluator-accounts")
        assert accounts.status_code == 200
        items = accounts.json()["items"]
        logins = {row["login_id"]: row for row in items}
        assert logins["대우청라-박명식"]["role"] == "소장"
        assert logins["대우청라-김팀장"]["role"] == "팀장"
        assert logins["대우청라-김팀장"]["assigned_worker_count"] == 1


def test_ceo_pending_list_allows_ceo_login_id(tmp_path: Path):
    from app.modules.functional_eval.constants import CEO_EVAL_LOGIN_IDS

    db_file = tmp_path / "fe_ceo_list.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    ceo_login = next(iter(CEO_EVAL_LOGIN_IDS))
    setup_db = TestingSessionLocal()
    setup_db.add(
        User(
            id=99,
            name="김홍수",
            login_id=ceo_login,
            password_hash="x",
            role=Role.HQ_SAFE_ADMIN,
            ui_type=UIType.HQ_SAFE,
            site_id=None,
        )
    )
    period = FunctionalEvalPeriod(title="test", deadline_date=date(2026, 12, 31), is_active=True)
    setup_db.add(period)
    setup_db.flush()
    from app.modules.functional_eval.approval_workflow import get_or_create_site_approval
    from app.modules.functional_eval.constants import APPROVAL_STATUS_HQ_APPROVED

    row = get_or_create_site_approval(setup_db, period.id, "24025")
    row.status = APPROVAL_STATUS_HQ_APPROVED
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(functional_eval_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    ceo_user = SimpleNamespace(
        id=99,
        role=Role.HQ_SAFE_ADMIN,
        ui_type=UIType.HQ_SAFE,
        site_id=None,
        login_id=ceo_login,
        name="김홍수",
    )
    app.dependency_overrides[get_current_user_with_bypass] = lambda: ceo_user
    client = TestClient(app)
    res = client.get("/functional-eval/hq/ceo-approvals/pending")
    assert res.status_code == 200
    assert any(item.get("site_code") == "24025" for item in res.json().get("items") or [])


def test_sanction_auto_applies_safety_c_and_requires_note(tmp_path: Path):
    db_file = tmp_path / "sanction_c.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.functional_eval.eval_catalog import build_lowest_grade_scores
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="24018", site_name="테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    manager = User(
        id=10,
        name="소장",
        login_id="24018",
        password_hash="x",
        role=Role.SITE_FUNCTIONAL_EVAL,
        ui_type=UIType.SITE,
        site_id=site.id,
        must_change_password=False,
    )
    setup_db.add(manager)
    period = FunctionalEvalPeriod(title="test", deadline_date=date(2026, 12, 31), is_active=True)
    setup_db.add(period)
    setup_db.flush()
    worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24018",
        row_no=1,
        name="홍길동",
        rrn_hash=hashlib.sha256(b"8804091170112").hexdigest(),
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add(worker)
    setup_db.flush()
    _seed_attendance(setup_db, period, worker)
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=10,
        role=Role.SITE_FUNCTIONAL_EVAL,
        ui_type=UIType.SITE,
        site_id=site_id,
        login_id="24018",
        name="소장",
    )
    client = TestClient(app)

    missing_note = client.post(
        "/functional-eval/sanctions",
        data={
            "worker_id": str(worker_id),
            "violation_code": "INST_TBM",
            "evidence_type": "COMMENT",
            "note": "",
            "signature_data": _TEST_SIGNATURE_DATA,
        },
    )
    assert missing_note.status_code == 400

    safety_res = _save_safety_with_single_bottom(client, worker_id, "c2")
    assert safety_res.status_code == 200
    saved_scores = safety_res.json()["assessment"]["scores"]

    res = _post_sanction(client, worker_id=worker_id, violation_code="INST_QR_ACTIVITY", note="QR 미이행")
    assert res.status_code == 200
    body = res.json()
    assert body["reported_by_name"] == "소장"
    assert body["note"] == "QR 미이행"
    assert body["penalty_points"] == 0
    assert body["has_signature"] is True

    safety = client.get(f"/functional-eval/workers/{worker_id}/assessment/SAFETY")
    assert safety.status_code == 200
    assessment = safety.json()["assessment"]
    assert assessment["scores"] == saved_scores

    revisions = client.get(f"/functional-eval/workers/{worker_id}/assessment-revisions")
    assert revisions.status_code == 200
    assert len(revisions.json()["items"]) == 0

    second = _post_sanction(client, worker_id=worker_id, violation_code="INST_TBM", note="TBM 2차")
    assert second.status_code == 200
    assert second.json()["penalty_points"] == 0

    safety2 = client.get(f"/functional-eval/workers/{worker_id}/assessment/SAFETY")
    assert safety2.json()["assessment"]["scores"]["c1"] == "BOTTOM"

    revisions2 = client.get(f"/functional-eval/workers/{worker_id}/assessment-revisions")
    assert revisions2.status_code == 200
    assert any(item.get("source") == "SANCTION_AUTO" for item in revisions2.json()["items"])

    third = _post_sanction(client, worker_id=worker_id, violation_code="INST_QR_ACTIVITY", note="QR 2차")
    assert third.status_code == 200
    assert third.json()["penalty_points"] == 5

    safety3 = client.get(f"/functional-eval/workers/{worker_id}/assessment/SAFETY")
    safety3_body = safety3.json()["assessment"]
    assert safety3_body["scores"]["c2"] == "BOTTOM"
    assert safety3_body.get("adjustment_penalty") == 5
    assert safety3_body["total_score"] == safety3_body["base_total_score"] - 5

    workers_res = client.get("/functional-eval/my-site/workers")
    worker_row = next(item for item in workers_res.json()["items"] if item["id"] == worker_id)
    assert worker_row["safety_assessment"]["adjustment_penalty"] == 5

    revisions3 = client.get(f"/functional-eval/workers/{worker_id}/assessment-revisions")
    assert sum(1 for item in revisions3.json()["items"] if item.get("source") == "SANCTION_AUTO") == 1


def test_manager_can_sanction_team_worker(tmp_path: Path):
    db_file = tmp_path / "manager_team_sanction.db"
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
    team_worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24018",
        row_no=2,
        name="팀원",
        rrn_hash=hashlib.sha256(b"9001011234567").hexdigest(),
        assigned_evaluator_login_id="24018-팀장A",
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add(team_worker)
    setup_db.flush()
    _seed_attendance(setup_db, period, team_worker)
    site_id = site.id
    team_worker_id = team_worker.id
    setup_db.close()

    app = FastAPI()
    app.include_router(functional_eval_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=10,
        role=Role.SITE_FUNCTIONAL_EVAL,
        ui_type=UIType.SITE,
        site_id=site_id,
        login_id="24018",
        name="소장",
    )
    client = TestClient(app)

    res = _post_sanction(
        client,
        worker_id=team_worker_id,
        violation_code="GEN_BASIC_SAFETY",
        note="팀원 안전수칙 위반",
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("worker_id") == team_worker_id or body.get("id")


def test_hq_assessment_override_with_reason(tmp_path: Path):
    db_file = tmp_path / "hq_override.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.functional_eval.eval_catalog import get_criteria
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    setup_db.add(
        User(
            id=20,
            name="안전보건",
            login_id="안전보건-테스트",
            password_hash="x",
            role=Role.HQ_SAFE,
            ui_type=UIType.HQ_SAFE,
            site_id=None,
            must_change_password=False,
        )
    )
    period = FunctionalEvalPeriod(title="test", deadline_date=date(2026, 12, 31), is_active=True)
    setup_db.add(period)
    setup_db.flush()
    worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24018",
        row_no=1,
        name="홍길동",
        rrn_hash=hashlib.sha256(b"8804091170112").hexdigest(),
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add(worker)
    setup_db.commit()
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=20,
        role=Role.HQ_SAFE,
        ui_type=UIType.HQ_SAFE,
        site_id=None,
        login_id="안전보건-테스트",
        name="안전보건",
    )
    client = TestClient(app)

    criteria = get_criteria("FUNCTIONAL")
    scores = {c["id"]: c["grades"][0]["key"] for c in criteria}

    missing_reason = client.put(
        f"/functional-eval/hq/workers/{worker_id}/assessment/FUNCTIONAL",
        json={"scores": scores},
    )
    assert missing_reason.status_code == 422

    res = client.put(
        f"/functional-eval/hq/workers/{worker_id}/assessment/FUNCTIONAL",
        json={"scores": scores, "reason": "현장 요청에 따른 본사 조정"},
    )
    assert res.status_code == 200
    assert res.json()["assessment"]["is_complete"] is True

    revisions = client.get(f"/functional-eval/workers/{worker_id}/assessment-revisions")
    assert revisions.status_code == 200
    assert revisions.json()["items"][0]["source"] == "HQ_OVERRIDE"
    assert revisions.json()["items"][0]["edited_by_name"] == "안전보건"


def test_parse_erp_site_team_prefix():
    from app.modules.functional_eval.site_alias import parse_erp_site_team_prefix

    info = parse_erp_site_team_prefix("[1.대우건설] 청라C18BL 오피스텔")
    assert info["team_no"] == 1
    assert info["team_label"] == "공사1팀"
    assert info["contractor_label"] == "대우건설"

    info2 = parse_erp_site_team_prefix("[2.한화건설] 마곡 프로젝트")
    assert info2["team_no"] == 2
    assert info2["team_key"] == "2"


def test_hq_grade_stats(tmp_path: Path):
    db_file = tmp_path / "functional_eval_grade_stats.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.functional_eval import models as functional_eval_models  # noqa: F401
    from app.modules.functional_eval.eval_catalog import build_top_grade_scores
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="24025", site_name="대우청라")
    setup_db.add(site)
    setup_db.flush()
    setup_db.add(
        User(
            id=20,
            name="본사",
            login_id="hq1",
            password_hash="x",
            role=Role.HQ_SAFE,
            ui_type=UIType.HQ_SAFE,
            must_change_password=False,
        )
    )
    setup_db.add(
        User(
            id=21,
            name="소장",
            login_id="24025",
            password_hash="x",
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site.id,
            must_change_password=False,
        )
    )
    period = FunctionalEvalPeriod(title="test", deadline_date=date(2026, 6, 26), is_active=True)
    period.grade_stats_live_from = date(2026, 1, 1)
    setup_db.add(period)
    setup_db.flush()
    setup_db.add(
        FunctionalEvalSiteRegistry(
            site_code="24025",
            erp_site_label="[1.대우건설] 청라C18BL",
            site_alias="대우청라",
            manager_name="박명식",
            manager_login_id="대우청라-박명식",
            erp_headcount=32,
        )
    )
    worker = FunctionalEvalWorker(
        period_id=period.id,
        site_code="24025",
        site_name="[1.대우건설] 청라C18BL",
        row_no=2,
        name="이근로",
        rrn_hash=hashlib.sha256(b"9001011234567").hexdigest(),
        is_site_manager=False,
        is_active=True,
    )
    setup_db.add(worker)
    setup_db.flush()
    _seed_attendance(setup_db, period, worker)
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

    hq_user = SimpleNamespace(id=20, role=Role.HQ_SAFE, ui_type=UIType.HQ_SAFE, site_id=None, login_id="hq1")
    site_user = SimpleNamespace(id=21, role=Role.SITE_FUNCTIONAL_EVAL, ui_type=UIType.SITE, site_id=site_id, login_id="24025")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: site_user
    site_client = TestClient(app)
    scores = build_top_grade_scores("FUNCTIONAL")
    site_client.put(f"/functional-eval/workers/{worker_id}/assessment/FUNCTIONAL", json={"scores": scores})
    site_client.put(f"/functional-eval/workers/{worker_id}/assessment/SAFETY", json={"scores": build_top_grade_scores("SAFETY")})

    app.dependency_overrides[get_current_user_with_bypass] = lambda: hq_user
    client = TestClient(app)
    res = client.get("/functional-eval/hq/grade-stats")
    assert res.status_code == 200
    body = res.json()
    assert body["overall"]["functional"]["graded_total"] == 1
    assert body["overall"]["functional"]["workers_total"] == 1
    assert body["overall"]["functional"]["erp_headcount"] == 32
    assert body["overall"]["functional"]["grades"]["S"]["pct"] == 100.0
    assert body["by_team"][0]["team_no"] == 1
    assert body["by_site"][0]["site_code"] == "24025"

    site_res = client.get("/functional-eval/hq/sites/24025/grade-stats")
    assert site_res.status_code == 200
    assert site_res.json()["team_label"] == "공사1팀"

    app.dependency_overrides[get_current_user_with_bypass] = lambda: site_user
    my_res = site_client.get("/functional-eval/my-site/grade-stats")
    assert my_res.status_code == 200
    assert my_res.json()["functional"]["grades"]["S"]["count"] == 1
