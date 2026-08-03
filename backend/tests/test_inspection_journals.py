from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.settings import settings
from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.main import app
from app.modules.inspection_journals.training_catalog import TRAINING_CATALOG


def _jpeg(width: int = 3000, height: int = 2000) -> bytes:
    stream = BytesIO()
    Image.new("RGB", (width, height), "white").save(stream, "JPEG", quality=90)
    return stream.getvalue()


def _client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=777,
        name="Safety User",
        login_id="safety-user",
        role=Role.HQ_SAFE,
        must_change_password=False,
    )
    monkeypatch.setattr(settings, "storage_root", tmp_path / "storage")
    return TestClient(app), testing_session


def test_training_catalog_matches_distinct_company_form_sheets():
    assert len(TRAINING_CATALOG) == 8
    assert "건강증진 및 질병 예방" in TRAINING_CATALOG["REGULAR"]["legal_content"]
    assert "75볼트" in TRAINING_CATALOG["SPECIAL_ELECTRICAL"]["legal_content"]
    assert "폭발 한계점" in TRAINING_CATALOG["SPECIAL_MSDS"]["legal_content"]
    assert "와이어로프" in TRAINING_CATALOG["SPECIAL_CRANE"]["legal_content"]
    assert "환기설비" in TRAINING_CATALOG["SPECIAL_CONFINED_SPACE"]["legal_content"]


def test_create_crop_resize_and_export_inspection_journal(tmp_path, monkeypatch):
    client, _session = _client(tmp_path, monkeypatch)
    catalog = client.get("/inspection-journals/training-catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()) == 8

    response = client.post(
        "/inspection-journals",
        data={
            "site_name": "Test Site",
            "subject": "Crane inspection",
            "inspected_on": "2026-08-03",
            "time_text": "07:00~09:00",
            "location": "B1 Core 2",
            "attendees": "Manager A\nWorker B",
            "instructor_name": "Instructor",
            "instructor_affiliation": "BooHyun",
            "training_code": "SPECIAL_CRANE",
            "additional_content": "Use proper safety hooks.",
            "special_notes": "Understanding confirmed.",
            "photo_metadata": '[{"rotation_degrees":90,"crop_left":0.1,"crop_top":0.05,"crop_right":0.1,"crop_bottom":0.05,"caption":"Inspection photo"}]',
        },
        files=[("photos", ("inspection.jpg", _jpeg(), "image/jpeg"))],
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["training_label"] == "특별교육 · 1톤 이상 크레인"
    assert "와이어로프" in payload["legal_content"]
    assert payload["photos"][0]["rotation_degrees"] == 90
    stored_images = list((tmp_path / "storage" / "inspection-journals" / "photos").glob("*.jpg"))
    assert len(stored_images) == 1
    with Image.open(stored_images[0]) as stored:
        assert max(stored.size) <= 2200

    pdf = client.get(f"/inspection-journals/{payload['id']}/pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 3000
    app.dependency_overrides.clear()
