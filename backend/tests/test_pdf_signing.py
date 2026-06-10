from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.enums import Role
from app.modules.pdf_signing.models import PdfSigningRequest
from app.modules.pdf_signing.routes import router as pdf_signing_router


def _minimal_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=595.2, height=841.68)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _png_1x1() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_pdf_signing_token_flow(tmp_path):
    db_file = tmp_path / "pdf_sign.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.pdf_signing import models as pdf_signing_models  # noqa: F401
    from app.core.database import Base

    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(pdf_signing_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1, role=Role.HQ_SAFE, site_id=None, login_id="hq01"
    )
    client = TestClient(app)

    pdf = _minimal_pdf_bytes()
    create_res = client.post(
        "/pdf-signing/requests",
        data={
            "signer_name": "테스트",
            "signer_title": "전무",
            "purpose_label": "시험",
            "expires_hours": "24",
        },
        files={"file": ("report.pdf", pdf, "application/pdf")},
        headers={"origin": "https://www.besma.co.kr"},
    )
    assert create_res.status_code == 200, create_res.text
    token = create_res.json()["token"]
    assert "/sign/" in create_res.json()["sign_url"]

    info_res = client.get(f"/pdf-signing/public/{token}")
    assert info_res.status_code == 200
    assert info_res.json()["status"] == "pending"

    doc_res = client.get(f"/pdf-signing/public/{token}/document")
    assert doc_res.status_code == 200
    assert doc_res.headers["content-type"] == "application/pdf"
    assert "inline" in doc_res.headers.get("content-disposition", "")

    png_b64 = base64.b64encode(_png_1x1()).decode()
    sign_res = client.post(
        f"/pdf-signing/public/{token}/sign",
        json={"signature_png_base64": png_b64},
        headers={"user-agent": "pytest"},
    )
    assert sign_res.status_code == 200, sign_res.text
    assert sign_res.json()["status"] == "signed"

    again = client.post(
        f"/pdf-signing/public/{token}/sign",
        json={"signature_png_base64": png_b64},
    )
    assert again.status_code == 409

    signed_doc = client.get(f"/pdf-signing/public/{token}/document")
    assert signed_doc.status_code == 409

    list_res = client.get("/pdf-signing/requests")
    assert list_res.status_code == 200
    row = list_res.json()[0]
    assert row["signed_sha256"]
    assert row["signer_ip"]

    dl = client.get(f"/pdf-signing/requests/{row['id']}/download", params={"kind": "signed"})
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/pdf"


def test_pdf_signing_temp_slot_flow(tmp_path):
    db_file = tmp_path / "pdf_sign_slot.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.pdf_signing import models as pdf_signing_models  # noqa: F401
    from app.core.database import Base

    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(pdf_signing_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1, role=Role.HQ_SAFE, site_id=None, login_id="hq01"
    )
    client = TestClient(app)

    pdf = _minimal_pdf_bytes()
    create_res = client.post(
        "/pdf-signing/slots/sign2",
        data={"signer_name": "테스트", "signer_title": "관리자", "expires_hours": "24"},
        files={"file": ("report.pdf", pdf, "application/pdf")},
        headers={"origin": "https://www.besma.co.kr"},
    )
    assert create_res.status_code == 200, create_res.text
    assert create_res.json()["slot"] == "sign2"
    assert create_res.json()["sign_url"].endswith("/temp/sign2")

    slots_res = client.get("/pdf-signing/slots")
    assert slots_res.status_code == 200
    by_slot = {row["slot"]: row for row in slots_res.json()}
    assert by_slot["sign2"]["request"]["status"] == "pending"

    info_res = client.get("/pdf-signing/public/slot/sign2")
    assert info_res.status_code == 200

    doc_res = client.get("/pdf-signing/public/slot/sign2/document")
    assert doc_res.status_code == 200
    assert doc_res.headers["content-type"] == "application/pdf"

    png_b64 = base64.b64encode(_png_1x1()).decode()
    sign_res = client.post(
        "/pdf-signing/public/slot/sign2/sign",
        json={"signature_png_base64": png_b64},
    )
    assert sign_res.status_code == 200, sign_res.text
