"""PDF 병합 업로드(일일 문서 + append_files / append_only) 회귀 테스트."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_submissions.routes import router as document_submissions_router
from app.modules.documents.models import Document
from app.modules.sites.models import Site
from app.modules.users.models import User


def _minimal_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_upload_merges_append_files_for_daily_tbm(tmp_path: Path):
    db_file = tmp_path / "merge_upload.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="M1", site_name="병합 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    setup_db.add(
        User(
            id=1,
            name="m",
            login_id="merge_site",
            password_hash="x",
            site_id=site_id,
            role=Role.SITE,
        )
    )
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(document_submissions_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1, role=Role.SITE, site_id=site_id, login_id="merge_site"
    )
    client = TestClient(app)

    today = date(2026, 4, 16).isoformat()
    pdf_main = _minimal_pdf_bytes()
    pdf_extra = _minimal_pdf_bytes()
    res = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "DAILY_TBM",
            "work_date": today,
        },
        files=[
            ("file", ("tbm.pdf", pdf_main, "application/pdf")),
            ("append_files", ("extra.pdf", pdf_extra, "application/pdf")),
        ],
    )
    assert res.status_code == 200, res.text
    doc_id = int(res.json()["document_id"])

    db_check = TestingSessionLocal()
    try:
        doc = db_check.query(Document).filter(Document.id == doc_id).first()
        assert doc is not None and doc.file_path
        merged_path = settings.storage_root / doc.file_path
        assert merged_path.exists()
        merged = merged_path.read_bytes()
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(merged))
        assert len(reader.pages) >= 2
    finally:
        db_check.close()


def test_append_only_after_submit(tmp_path: Path):
    db_file = tmp_path / "append_only.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="M2", site_name="append only 현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    setup_db.add(
        User(
            id=1,
            name="m",
            login_id="append_site",
            password_hash="x",
            site_id=site_id,
            role=Role.SITE,
        )
    )
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(document_submissions_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1, role=Role.SITE, site_id=site_id, login_id="append_site"
    )
    client = TestClient(app)

    today = date(2026, 4, 16).isoformat()
    pdf_main = _minimal_pdf_bytes()
    first = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "DAILY_TBM",
            "work_date": today,
        },
        files={"file": ("tbm.pdf", pdf_main, "application/pdf")},
    )
    assert first.status_code == 200, first.text
    instance_id = int(first.json()["instance_id"])

    db_mid = TestingSessionLocal()
    try:
        inst = db_mid.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
        assert inst is not None
        inst.workflow_status = WorkflowStatus.SUBMITTED
        db_mid.add(inst)
        db_mid.commit()
    finally:
        db_mid.close()

    pdf_extra = _minimal_pdf_bytes()
    second = client.post(
        "/document-submissions/upload",
        data={
            "instance_id": str(instance_id),
            "append_only": "true",
        },
        files=[("append_files", ("extra.pdf", pdf_extra, "application/pdf"))],
    )
    assert second.status_code == 200, second.text

    doc_id = int(second.json()["document_id"])
    db_check = TestingSessionLocal()
    try:
        doc = db_check.query(Document).filter(Document.id == doc_id).first()
        assert doc is not None and doc.file_path
        merged_path = settings.storage_root / doc.file_path
        merged = merged_path.read_bytes()
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(merged))
        assert len(reader.pages) >= 2
    finally:
        db_check.close()
