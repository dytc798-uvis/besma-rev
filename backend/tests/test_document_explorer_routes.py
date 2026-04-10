from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config.settings import settings
from app.core.auth import get_current_user_with_bypass
from app.core.enums import Role
from app.modules.document_explorer.routes import router as document_explorer_router


def test_document_explorer_list_and_search(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    storage_root = tmp_path / "storage"
    field_dir = storage_root / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    field_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "현장안전일지.pdf").write_text("dummy", encoding="utf-8")
    (docs_dir / "template" / "TBM_양식.xlsx").parent.mkdir(parents=True, exist_ok=True)
    (docs_dir / "template" / "TBM_양식.xlsx").write_text("dummy", encoding="utf-8")
    (docs_dir / "기본양식" / "표지.ai").parent.mkdir(parents=True, exist_ok=True)
    (docs_dir / "기본양식" / "표지.ai").write_text("dummy", encoding="utf-8")
    (docs_dir / "현장문서" / "제출_안전일지.hwp").parent.mkdir(parents=True, exist_ok=True)
    (docs_dir / "현장문서" / "제출_안전일지.hwp").write_text("dummy", encoding="utf-8")
    (field_dir / "instance_1_1710000000_일일서류.xlsx").write_text("dummy", encoding="utf-8")

    original_base_dir = settings.document_explorer_base_dir
    original_storage_root = settings.storage_root
    settings.document_explorer_base_dir = docs_dir
    settings.storage_root = storage_root

    app = FastAPI()
    app.include_router(document_explorer_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.HQ_SAFE,
        ui_type="HQ_SAFE",
    )
    client = TestClient(app)

    try:
        res = client.get("/document-explorer/list")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 1
        assert any(item["name"] == "현장안전일지.pdf" for item in items)
        assert all(item["extension"] == ".pdf" for item in items)

        search_res = client.get("/document-explorer/search", params={"q": "현장안전일지"})
        assert search_res.status_code == 200
        search_items = search_res.json()["items"]
        assert len(search_items) == 1
        assert search_items[0]["name"] == "현장안전일지.pdf"
    finally:
        settings.document_explorer_base_dir = original_base_dir
        settings.storage_root = original_storage_root


def test_document_explorer_file_open_and_not_found(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "template" / "TBM_양식.pdf").parent.mkdir(parents=True, exist_ok=True)
    file_path = docs_dir / "template" / "TBM_양식.pdf"
    file_path.write_text("dummy", encoding="utf-8")

    original_base_dir = settings.document_explorer_base_dir
    settings.document_explorer_base_dir = docs_dir

    app = FastAPI()
    app.include_router(document_explorer_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.HQ_SAFE,
        ui_type="HQ_SAFE",
    )
    client = TestClient(app)

    try:
        ok_res = client.get(
            "/document-explorer/file",
            params={"relative_path": "base/template/TBM_양식.pdf", "disposition": "inline"},
        )
        assert ok_res.status_code == 200
        assert "content-disposition" in {k.lower() for k in ok_res.headers.keys()}

        nf_res = client.get(
            "/document-explorer/file",
            params={"relative_path": "base/template/not-exists.xlsx", "disposition": "inline"},
        )
        assert nf_res.status_code == 404
    finally:
        settings.document_explorer_base_dir = original_base_dir

