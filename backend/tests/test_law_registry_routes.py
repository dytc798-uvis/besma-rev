from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.law_registry.routes import router as law_registry_router
from app.modules.law_registry.service import import_records


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


def _build_client(db):
    app = FastAPI()
    app.include_router(law_registry_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.HQ_SAFE,
        ui_type="HQ_SAFE",
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _seed_records(db) -> None:
    import_records(
        db,
        article_records=[
            {
                "law_name": "산업안전보건법",
                "law_type": "ACT",
                "article_display": "제5조",
                "summary_title": "사업주는 안전조치를 해야 한다",
                "department": "안전보건팀",
                "action_required": "정기 점검 실시",
                "countermeasure": "체크리스트 운영",
                "penalty": "벌금",
                "keywords": "안전, 점검",
                "risk_tags": "추락, 감전",
                "work_type_tags": "전기",
                "document_tags": "TBM",
                "sort_order": 1,
            },
            {
                "law_name": "산업안전보건법",
                "law_type": "ACT",
                "article_display": "제10조",
                "summary_title": "교육을 실시해야 한다",
                "department": "교육팀",
                "action_required": "안전교육 시행",
                "countermeasure": "교육일지 보관",
                "penalty": "과태료",
                "keywords": "교육",
                "risk_tags": "교육",
                "work_type_tags": "공통",
                "document_tags": "교육일지",
                "sort_order": 1,
            },
        ],
        revision_records=[],
    )


def test_law_registry_search_basic():
    db = _setup_db()
    _seed_records(db)
    client = _build_client(db)

    response = client.get("/law-registry/search", params={"q": "점검"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["law_name"] == "산업안전보건법"
    assert body["items"][0]["article_display"] == "제5조"


def test_law_registry_search_filters():
    db = _setup_db()
    _seed_records(db)
    client = _build_client(db)

    response = client.get(
        "/law-registry/search",
        params={
            "q": "안전",
            "department": "안전보건팀",
            "risk_tag": "추락",
            "document_tag": "TBM",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["department"] == "안전보건팀"


def test_law_registry_search_empty_result():
    db = _setup_db()
    _seed_records(db)
    client = _build_client(db)

    response = client.get("/law-registry/search", params={"q": "없는검색어"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
