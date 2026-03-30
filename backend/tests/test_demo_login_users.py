from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.enums import Role
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

    first = ensure_demo_login_users(db, password="Temp@1234", site_code="SITE002")
    second = ensure_demo_login_users(db, password="Temp@1234", site_code="SITE002")

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
    by_login = {user.login_id: user.name for user in db.query(User).all()}
    assert by_login["site01"] == "양규성"
    assert by_login["site03"] == "박규철"
