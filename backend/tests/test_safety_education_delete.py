from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.security import get_password_hash, verify_password
from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.safety_features.models import SafetyEducationMaterial
from app.modules.safety_features.routes import router as safety_features_router
from app.modules.users.models import User


def _build_client(tmp_path: Path, *, hq_password: str = "secret-hq") -> TestClient:
    db_file = tmp_path / "edu_del.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.safety_features import models as _sf  # noqa: F401
    from app.modules.workers import models as _worker_models  # noqa: F401
    from app.modules.documents import models as _document_models  # noqa: F401
    from app.modules.document_generation import models as _document_generation_models  # noqa: F401
    from app.modules.document_settings import models as _document_settings_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    storage = tmp_path / "storage"
    (storage / "documents").mkdir(parents=True, exist_ok=True)
    from app.config.settings import settings

    original_root = settings.storage_root
    settings.storage_root = storage

    db = SessionLocal()
    db.add(
        User(
            id=1,
            name="HQ Tester",
            login_id="hq_edu",
            password_hash=get_password_hash(hq_password),
            role=Role.HQ_SAFE,
            ui_type="HQ_SAFE",
            site_id=None,
            must_change_password=False,
        )
    )
    db.commit()
    db.close()

    def override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    app.include_router(safety_features_router)
    app.dependency_overrides[get_db] = override_db

    def user_factory():
        s = SessionLocal()
        try:
            u = s.query(User).filter(User.id == 1).first()
            assert u is not None
            return SimpleNamespace(
                id=u.id,
                login_id=u.login_id,
                name=u.name,
                password_hash=u.password_hash,
                role=u.role,
                ui_type=u.ui_type,
                site_id=u.site_id,
            )
        finally:
            s.close()

    app.dependency_overrides[get_current_user_with_bypass] = user_factory
    return TestClient(app), original_root, settings


def test_delete_education_wrong_password_then_success(tmp_path: Path):
    client, original_root, settings = _build_client(tmp_path)
    try:
        storage = tmp_path / "storage"
        rel = Path("documents") / "education_test.bin"
        full = storage / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(b"x")

        db_file = tmp_path / "edu_del.db"
        engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(bind=engine)
        s = SessionLocal()
        s.add(
            SafetyEducationMaterial(
                title="MSDS 샘플",
                site_id=None,
                file_path=rel.as_posix(),
                file_name="sample.bin",
                file_size=1,
                uploaded_by_user_id=1,
            )
        )
        s.commit()
        mid = s.query(SafetyEducationMaterial).first().id
        s.close()

        bad = client.post(f"/safety-features/education/{mid}/delete", json={"password": "wrong"})
        assert bad.status_code == 403

        ok = client.post(f"/safety-features/education/{mid}/delete", json={"password": "secret-hq"})
        assert ok.status_code == 200
        assert ok.json() == {"ok": True}

        log = client.get("/safety-features/education/deletions")
        assert log.status_code == 200
        items = log.json()["items"]
        assert len(items) == 1
        assert items[0]["material_id"] == mid
        assert items[0]["deleted_by_login"] == "hq_edu"
        assert items[0]["title"] == "MSDS 샘플"

        s2 = SessionLocal()
        assert s2.query(SafetyEducationMaterial).count() == 0
        s2.close()
        assert not full.exists()
    finally:
        settings.storage_root = original_root


def test_verify_password_fixture():
    h = get_password_hash("abc")
    assert verify_password("abc", h)
    assert not verify_password("ab", h)
