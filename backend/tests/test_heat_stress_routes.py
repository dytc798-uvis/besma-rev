from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.heat_stress.models import HeatStressAuditLog, HeatStressRecord
from app.modules.heat_stress.routes import router
from app.modules.sites.models import Site
from app.modules.workers.models import Person  # noqa: F401 - registers users.person_id FK target

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_site_create_confirm_pdf_and_scope(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'heat.db'}", connect_args={"check_same_thread": False})
    local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    with local() as db:
        db.add_all([
            Site(id=1, site_code="S1", site_name="첫 현장", status="ACTIVE"),
            Site(id=2, site_code="S2", site_name="둘 현장", status="ACTIVE"),
        ])
        db.commit()

    app = FastAPI()
    app.include_router(router)
    current = {"user": SimpleNamespace(id=10, name="점검자", role=Role.SITE, site_id=1)}

    def override_db():
        with local() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current["user"]
    client = TestClient(app)
    created = client.post("/heat-stress/records", json={
        "measured_at": datetime(2026, 7, 29, 14, 0).isoformat(),
        "work_location": "옥외",
        "work_process": "배관",
        "measurement_source": "ON_SITE",
        "air_temperature_c": 33,
        "relative_humidity_pct": 70,
        "actual_actions": ["WATER"],
        "action_notes": "휴식 확인 필요",
        "recorder_signature_data": PNG,
    })
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]
    assert created.json()["action_compliance"] == "ACTION_REQUIRED"
    assert created.json()["status"] == "CONFIRM_PENDING"

    repeated = client.post("/heat-stress/records", json={
        "measured_at": datetime(2026, 7, 29, 14, 0).isoformat(),
        "work_location": "옥외",
        "work_process": "배관",
        "measurement_source": "ON_SITE",
        "air_temperature_c": 33,
        "relative_humidity_pct": 70,
        "actual_actions": ["WATER"],
        "action_notes": "같은 날 추가 측정",
        "recorder_signature_data": PNG,
    })
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] != record_id

    current["user"] = SimpleNamespace(id=11, name="다른 현장", role=Role.SITE, site_id=2)
    assert client.get(f"/heat-stress/records/{record_id}").status_code == 403

    current["user"] = SimpleNamespace(id=12, name="현장소장", role=Role.SITE, site_id=1)
    confirmed = client.post(f"/heat-stress/records/{record_id}/confirm", json={
        "confirmer_name": "현장소장",
        "confirmer_title": "현장소장",
        "confirmer_signature_data": PNG,
    })
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "CONFIRMED"
    pdf = client.get(f"/heat-stress/records/{record_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF-")

    current["user"] = SimpleNamespace(id=13, name="일반본사", role=Role.HQ_OTHER, site_id=None)
    assert client.get(f"/heat-stress/records/{record_id}/pdf").status_code == 200

    with local() as db:
        assert db.query(HeatStressRecord).count() == 2
        assert db.query(HeatStressAuditLog).count() == 5
