from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.document_submissions.routes import router as document_submissions_router
from app.modules.documents.ledger_managed import LEDGER_MANAGED_COMMUNICATION_MESSAGE
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.routes import router as documents_router
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.sites.models import Site
from app.modules.users.models import User


def _build_app(tmp_path: Path) -> tuple[TestClient, int, int, int]:
    db_file = tmp_path / "ledger_guard.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = Session()
    site = Site(site_code="S-LEDGER-001", site_name="Ledger guard test")
    db.add(site)
    db.flush()
    site_id = site.id

    cycle = SubmissionCycle(code="ADHOC", name="Adhoc", sort_order=0, is_active=True, is_auto_generatable=True)
    db.add(cycle)
    db.flush()
    dtm = DocumentTypeMaster(
        code="AUTO_WORKER_OPINION_LOG",
        name="Opinion log",
        sort_order=0,
        is_active=True,
        default_cycle_id=cycle.id,
    )
    db.add(dtm)
    db.flush()
    req = DocumentRequirement(
        site_id=site_id,
        document_type_id=dtm.id,
        is_enabled=True,
        code="AUTO_WORKER_OPINION_LOG",
        title="근로자의견청취",
        frequency="ROLLING",
        is_required=True,
        display_order=0,
    )
    db.add(req)
    db.add_all(
        [
            User(
                id=1,
                name="site",
                login_id="site_ledger_test",
                password_hash="x",
                site_id=site_id,
                role=Role.SITE,
            ),
            User(
                id=2,
                name="hq",
                login_id="hq_ledger_test",
                password_hash="x",
                site_id=site_id,
                role=Role.HQ_SAFE,
            ),
        ]
    )
    db.flush()
    req_id = req.id
    doc = Document(
        document_no="DOC-LEDGER-1",
        title="Ledger managed doc",
        document_type="AUTO_WORKER_OPINION_LOG",
        site_id=site_id,
        submitter_user_id=1,
        current_status=DocumentStatus.SUBMITTED,
        description=None,
        source_type="MANUAL",
        version_no=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(doc)
    db.commit()
    doc_id = doc.id
    db.close()

    app = FastAPI()
    app.include_router(document_submissions_router)
    app.include_router(documents_router)

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    current = {"user": SimpleNamespace(id=1, role=Role.SITE, site_id=site_id, login_id="site_ledger_test")}
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current["user"]

    return TestClient(app), site_id, req_id, doc_id


def test_document_submissions_upload_ledger_managed_409(tmp_path: Path):
    client, site_id, _, _ = _build_app(tmp_path)
    res = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "AUTO_WORKER_OPINION_LOG",
            "work_date": date(2026, 4, 13).isoformat(),
        },
        files={"file": ("x.txt", b"noop", "text/plain")},
    )
    assert res.status_code == 409
    assert res.json().get("detail") == LEDGER_MANAGED_COMMUNICATION_MESSAGE


def test_documents_history_ledger_managed_409(tmp_path: Path):
    client, site_id, req_id, _ = _build_app(tmp_path)
    res = client.get("/documents/history", params={"site_id": site_id, "requirement_id": req_id})
    assert res.status_code == 409
    assert res.json().get("detail") == LEDGER_MANAGED_COMMUNICATION_MESSAGE


def test_documents_comments_ledger_managed_409(tmp_path: Path):
    client, site_id, _, doc_id = _build_app(tmp_path)
    res = client.get(f"/documents/{doc_id}/comments")
    assert res.status_code == 409
    assert res.json().get("detail") == LEDGER_MANAGED_COMMUNICATION_MESSAGE
