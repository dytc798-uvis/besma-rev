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
    assert saved["grade_code"] in {"S", "A", "B", "C", "D"}

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
