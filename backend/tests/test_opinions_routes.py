from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.opinions.models import Opinion, OpinionStatus
from app.modules.opinions.routes import router as opinions_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _seed(db):
    site = Site(site_code="SITE001", site_name="현장1")
    db.add(site)
    db.flush()
    author = User(
        name="작성자",
        login_id="author1",
        password_hash="x",
        role=Role.HQ_SAFE,
        ui_type="HQ_SAFE",
        site_id=None,
        must_change_password=False,
    )
    other = User(
        name="타인",
        login_id="other1",
        password_hash="x",
        role=Role.HQ_SAFE,
        ui_type="HQ_SAFE",
        site_id=None,
        must_change_password=False,
    )
    db.add_all([author, other])
    db.commit()
    db.refresh(author)
    db.refresh(other)

    op = Opinion(
        site_id=site.id,
        category="운영 아이디어",
        content="테스트 제안",
        reporter_type="본사",
        status=OpinionStatus.RECEIVED,
        created_by_user_id=author.id,
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return author, other, op


def _client(db, *, user: User):
    app = FastAPI()
    app.include_router(opinions_router)

    app.dependency_overrides[get_current_user_with_bypass] = lambda: user

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_list_opinions_includes_created_by_user_id():
    db = _setup_db()
    author, _, opinion = _seed(db)
    client = _client(db, user=author)
    res = client.get("/opinions")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == opinion.id
    assert data[0]["created_by_user_id"] == author.id


def test_author_can_delete_own_opinion():
    db = _setup_db()
    author, _, opinion = _seed(db)
    client = _client(db, user=author)
    res = client.delete(f"/opinions/{opinion.id}")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert db.query(Opinion).filter(Opinion.id == opinion.id).first() is None


def test_non_author_cannot_delete():
    db = _setup_db()
    _, other, opinion = _seed(db)
    client = _client(db, user=other)
    res = client.delete(f"/opinions/{opinion.id}")
    assert res.status_code == 403
    assert db.query(Opinion).filter(Opinion.id == opinion.id).first() is not None
