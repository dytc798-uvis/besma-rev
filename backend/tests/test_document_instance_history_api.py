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
from app.modules.document_generation.models import DocumentInstance, DocumentInstanceStatus, WorkflowStatus
from app.modules.document_instances.routes import router as document_instances_router
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.documents.models import Document, DocumentStatus, DocumentUploadHistory
from app.modules.sites.models import Site
from app.modules.users.models import User


def test_document_instance_history_contract(tmp_path: Path):
    db_file = tmp_path / "inst_hist.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    site = Site(site_code="S-HIST-01", site_name="Hist Test Site")
    db.add(site)
    db.flush()

    cycle = SubmissionCycle(code="DAILY", name="일간", sort_order=1, is_auto_generatable=True)
    db.add(cycle)
    db.flush()
    dt = DocumentTypeMaster(
        code="TYPE_HIST_A",
        name="Test Doc Type",
        default_cycle_id=cycle.id,
        generation_rule="DAILY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    db.add(dt)
    db.flush()
    req = DocumentRequirement(
        site_id=site.id,
        document_type_id=dt.id,
        code="TYPE_HIST_A",
        title="Requirement Title A",
        frequency="DAILY",
        is_required=True,
        is_enabled=True,
        display_order=1,
    )
    db.add(req)
    db.flush()

    past_start = date(2026, 1, 1)
    past_end = date(2026, 1, 1)
    inst_missing = DocumentInstance(
        site_id=site.id,
        document_type_code="TYPE_HIST_A",
        period_start=past_start,
        period_end=past_end,
        generation_anchor_date=past_start,
        due_date=past_end,
        status=DocumentInstanceStatus.GENERATED,
        status_reason="OK",
        selected_requirement_id=req.id,
        workflow_status=WorkflowStatus.NOT_SUBMITTED,
        period_basis="AS_OF_FALLBACK",
        rule_is_required=True,
    )
    db.add(inst_missing)
    db.flush()

    hq = User(
        name="hq",
        login_id="hq_hist",
        password_hash="x",
        site_id=None,
        role=Role.HQ_SAFE,
    )
    site_u = User(
        name="site",
        login_id="site_hist",
        password_hash="x",
        site_id=site.id,
        role=Role.SITE,
    )
    db.add_all([hq, site_u])
    db.commit()
    inst_missing_id = inst_missing.id
    hq_id = hq.id
    site_user_id = site_u.id
    site_pk = site.id
    requirement_id = req.id
    db.close()

    app = FastAPI()
    app.include_router(document_instances_router)

    def override_get_db():
        local = TestingSessionLocal()
        try:
            yield local
        finally:
            local.close()

    app.dependency_overrides[get_db] = override_get_db
    user_holder: dict[str, object] = {
        "u": SimpleNamespace(id=hq_id, role=Role.HQ_SAFE, site_id=None),
    }

    def user_dep():
        return user_holder["u"]

    app.dependency_overrides[get_current_user_with_bypass] = user_dep
    client = TestClient(app)

    user_holder["u"] = SimpleNamespace(id=site_user_id, role=Role.SITE, site_id=site_pk)
    r_site = client.get("/document-instances/history")
    assert r_site.status_code == 403
    r_detail_site = client.get(f"/document-instances/{inst_missing_id}")
    assert r_detail_site.status_code == 403

    user_holder["u"] = SimpleNamespace(id=hq_id, role=Role.HQ_SAFE, site_id=None)
    r_hist = client.get("/document-instances/history", params={"site_id": site_pk, "limit": 50})
    assert r_hist.status_code == 200
    body = r_hist.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 1
    row = next(x for x in body["items"] if x["instance_id"] == inst_missing_id)
    assert row["workflow_status"] == WorkflowStatus.NOT_SUBMITTED
    assert row["document_id"] is None
    assert row["is_missing"] is True
    assert row["submission_count"] == 0
    assert row["reupload_count"] == 0
    assert row["document_name"] == "Requirement Title A"
    assert row["site_name"] == "Hist Test Site"
    assert row["period_label"] == "2026-01-01 ~ 2026-01-01"
    assert row["review_result"] is None

    r_sum = client.get("/document-instances/history/summary", params={"site_id": site_pk})
    assert r_sum.status_code == 200
    s = r_sum.json()
    assert s["total_instances"] >= 1
    assert s["missing_count"] >= 1
    assert "completion_rate" in s

    # Document + upload history
    db = TestingSessionLocal()
    inst2 = DocumentInstance(
        site_id=site_pk,
        document_type_code="TYPE_HIST_A",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 1),
        generation_anchor_date=date(2026, 2, 1),
        due_date=date(2026, 2, 1),
        status=DocumentInstanceStatus.GENERATED,
        status_reason="OK",
        selected_requirement_id=requirement_id,
        workflow_status=WorkflowStatus.SUBMITTED,
        period_basis="AS_OF_FALLBACK",
        rule_is_required=True,
    )
    db.add(inst2)
    db.flush()
    doc = Document(
        document_no="DOC-HIST-1",
        title="Uploaded",
        document_type="TYPE_HIST_A",
        site_id=site_pk,
        submitter_user_id=site_user_id,
        current_status=DocumentStatus.SUBMITTED,
        instance_id=inst2.id,
        submitted_at=datetime(2026, 2, 1, 10, 0, 0),
        uploaded_at=datetime(2026, 2, 1, 10, 0, 0),
        uploaded_by_user_id=site_user_id,
        version_no=1,
    )
    db.add(doc)
    db.flush()
    db.add(
        DocumentUploadHistory(
            document_id=doc.id,
            instance_id=inst2.id,
            version_no=1,
            action_type="UPLOAD",
            document_status=DocumentStatus.SUBMITTED,
            uploaded_at=doc.uploaded_at,
        )
    )
    db.add(
        DocumentUploadHistory(
            document_id=doc.id,
            instance_id=inst2.id,
            version_no=2,
            action_type="UPLOAD",
            document_status=DocumentStatus.SUBMITTED,
            uploaded_at=datetime(2026, 2, 2, 10, 0, 0),
        )
    )
    db.commit()
    inst2_id = inst2.id
    doc_pk = doc.id
    db.close()

    r2 = client.get("/document-instances/history", params={"site_id": site_pk})
    row2 = next(x for x in r2.json()["items"] if x["instance_id"] == inst2_id)
    assert row2["document_id"] == doc_pk
    assert row2["workflow_status"] == WorkflowStatus.SUBMITTED
    assert row2["submission_count"] == 2
    assert row2["reupload_count"] == 1
    assert row2["is_missing"] is False

    r_detail = client.get(f"/document-instances/{inst_missing_id}")
    assert r_detail.status_code == 200
    d_body = r_detail.json()
    assert d_body["instance_id"] == inst_missing_id
    assert d_body["site_id"] == site_pk
    assert d_body["document_type_code"] == "TYPE_HIST_A"
    assert d_body["workflow_status"] == WorkflowStatus.NOT_SUBMITTED
    assert d_body["document_id"] is None
    assert "period_label" in d_body and "submission_count" in d_body

    r_detail2 = client.get(f"/document-instances/{inst2_id}")
    assert r_detail2.status_code == 200
    assert r_detail2.json()["document_id"] == doc_pk
    assert r_detail2.json()["submission_count"] == 2

    r_404 = client.get("/document-instances/999999999")
    assert r_404.status_code == 404
