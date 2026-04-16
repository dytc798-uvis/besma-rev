from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.security import get_password_hash, verify_password
from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.seed.demo_login_users import ensure_demo_login_users


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

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_ensure_demo_login_users_is_idempotent_and_links_site_users():
    db = _setup_db()

    first = ensure_demo_login_users(db, password="temp@12", site_code="SITE002")
    second = ensure_demo_login_users(db, password="temp@12", site_code="SITE002")

    assert first.site_code == "SITE002"
    assert second.site_id == first.site_id
    assert db.query(User).filter(User.login_id.in_(["hq01", "hq02", "hq03", "hq04", "hq05"])).count() == 5
    assert db.query(User).filter(User.login_id.in_(["site01", "site02", "site03"])).count() == 3

    site_users = db.query(User).filter(User.role == Role.SITE).all()
    assert len([user for user in site_users if user.login_id in {"site01", "site02", "site03"}]) == 3
    assert all(user.site_id == first.site_id for user in site_users if user.login_id in {"site01", "site02", "site03"})
    assert all(user.is_active for user in db.query(User).all())
    assert all(user.must_change_password is False for user in db.query(User).all() if user.login_id in {"hq01", "hq02", "hq03", "hq04", "hq05", "site01", "site02", "site03"})
    assert db.query(Site).count() == 1
    assert all(item.verified_password for item in second.users)
    hq01 = db.query(User).filter(User.login_id == "hq01").first()
    assert hq01 is not None
    assert verify_password("1234", hq01.password_hash)
    hq02 = db.query(User).filter(User.login_id == "hq02").first()
    assert hq02 is not None
    assert verify_password("temp@12", hq02.password_hash)
    by_login = {user.login_id: user.name for user in db.query(User).all()}
    assert by_login["site01"] == "양규성"
    assert by_login["site03"] == "박규철"


def test_demo_login_users_replaces_legacy_hq01_to_hq03_and_case_collisions():
    db = _setup_db()
    for lid, name in (("hq01", "구버전A"), ("hq02", "구버전B"), ("hq03", "구버전C")):
        db.add(
            User(
                name=name,
                login_id=lid,
                password_hash=get_password_hash("legacy"),
                role=Role.HQ_SAFE,
                ui_type=UIType.HQ_SAFE,
                site_id=None,
                department="안전보건실",
                must_change_password=False,
            )
        )
    db.add(
        User(
            name="wrong-case",
            login_id="HQ01",
            password_hash=get_password_hash("x"),
            role=Role.HQ_SAFE,
            ui_type=UIType.HQ_SAFE,
            site_id=None,
            department="안전보건실",
            must_change_password=False,
        )
    )
    db.commit()

    ensure_demo_login_users(db, password="temp@12", site_code="SITE002")

    assert db.query(User).filter(User.login_id == "HQ01").count() == 0
    u1 = db.query(User).filter(User.login_id == "hq01").first()
    assert u1 is not None
    assert u1.name == "정상익"
    u2 = db.query(User).filter(User.login_id == "hq02").first()
    assert u2 is not None
    assert u2.name == "엄재복"
    u3 = db.query(User).filter(User.login_id == "hq03").first()
    assert u3 is not None
    assert u3.name == "김복수"
    assert db.query(User).filter(User.login_id.in_(["hq01", "hq02", "hq03", "hq04", "hq05"])).count() == 5
