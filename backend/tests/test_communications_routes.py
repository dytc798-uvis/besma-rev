from __future__ import annotations

import io
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.communications.routes import router as communications_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.communications import models as communication_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _seed_users(db):
    site1 = Site(site_code="SITE001", site_name="현장1")
    site2 = Site(site_code="SITE002", site_name="현장2")
    db.add_all([site1, site2])
    db.flush()

    sender = User(
        name="송신자",
        login_id="site_sender",
        password_hash="x",
        role=Role.SITE,
        ui_type="SITE",
        site_id=site1.id,
        must_change_password=False,
    )
    receiver = User(
        name="수신자",
        login_id="site_receiver",
        password_hash="x",
        role=Role.SITE,
        ui_type="SITE",
        site_id=site1.id,
        must_change_password=False,
    )
    other_site_user = User(
        name="타현장",
        login_id="site_other",
        password_hash="x",
        role=Role.SITE,
        ui_type="SITE",
        site_id=site2.id,
        must_change_password=False,
    )
    db.add_all([sender, receiver, other_site_user])
    db.commit()
    return sender, receiver, other_site_user


def _build_client(db, *, user_id: int, site_id: int):
    app = FastAPI()
    app.include_router(communications_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=user_id,
        role=Role.SITE.value,
        ui_type="SITE",
        site_id=site_id,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _make_image_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1600, 900), color)
    out = io.BytesIO()
    image.save(out, format="JPEG")
    return out.getvalue()


def test_create_list_and_mark_read():
    db = _setup_db()
    sender, receiver, _ = _seed_users(db)

    sender_client = _build_client(db, user_id=sender.id, site_id=sender.site_id)
    create_res = sender_client.post(
        "/communications",
        data={
            "title": "현장 사진 공유",
            "description": "장비 점검 전 사진",
            "receiver_user_ids": [str(receiver.id)],
        },
        files=[
            ("files", ("p1.jpg", _make_image_bytes((200, 120, 80)), "image/jpeg")),
            ("files", ("p2.jpg", _make_image_bytes((80, 120, 200)), "image/jpeg")),
        ],
    )
    assert create_res.status_code == 200
    comm_id = create_res.json()["id"]

    receiver_client = _build_client(db, user_id=receiver.id, site_id=receiver.site_id)
    unread_res = receiver_client.get("/communications/unread-count")
    assert unread_res.status_code == 200
    assert unread_res.json()["unread_count"] == 1

    list_res = receiver_client.get("/communications")
    assert list_res.status_code == 200
    body = list_res.json()
    assert len(body) == 1
    assert body[0]["id"] == comm_id
    assert body[0]["is_read"] is False
    assert len(body[0]["attachments"]) == 2
    assert body[0]["bundle_pdf_download_url"] == f"/communications/{comm_id}/bundle-pdf/download"

    pdf_res = receiver_client.get(body[0]["bundle_pdf_download_url"])
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"].startswith("application/pdf")

    mark_res = receiver_client.post(f"/communications/{comm_id}/read")
    assert mark_res.status_code == 200

    unread_res_after = receiver_client.get("/communications/unread-count")
    assert unread_res_after.json()["unread_count"] == 0


def test_create_rejects_other_site_receiver():
    db = _setup_db()
    sender, _, other_site_user = _seed_users(db)
    sender_client = _build_client(db, user_id=sender.id, site_id=sender.site_id)

    create_res = sender_client.post(
        "/communications",
        data={"receiver_user_ids": [str(other_site_user.id)]},
        files=[("files", ("p1.jpg", _make_image_bytes((120, 120, 120)), "image/jpeg"))],
    )
    assert create_res.status_code == 400
    assert "same site" in create_res.json()["detail"]

