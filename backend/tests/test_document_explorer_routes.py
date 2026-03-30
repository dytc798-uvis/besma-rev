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
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "현장안전일지.pdf").write_text("dummy", encoding="utf-8")
    (docs_dir / "template" / "TBM_양식.xlsx").parent.mkdir(parents=True, exist_ok=True)
    (docs_dir / "template" / "TBM_양식.xlsx").write_text("dummy", encoding="utf-8")
    (docs_dir / "기본양식" / "표지.ai").parent.mkdir(parents=True, exist_ok=True)
    (docs_dir / "기본양식" / "표지.ai").write_text("dummy", encoding="utf-8")
    (docs_dir / "현장문서" / "제출_안전일지.hwp").parent.mkdir(parents=True, exist_ok=True)
    (docs_dir / "현장문서" / "제출_안전일지.hwp").write_text("dummy", encoding="utf-8")

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
        res = client.get("/document-explorer/list")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 4
        assert any(item["name"] == "현장안전일지.pdf" for item in items)
        assert any(item["relative_path"] == "template/TBM_양식.xlsx" for item in items)
        assert any(item["relative_path"] == "기본양식/표지.ai" and item["category"] == "template" for item in items)
        assert any(item["relative_path"] == "현장문서/제출_안전일지.hwp" and item["category"] == "field" for item in items)

        search_res = client.get("/document-explorer/search", params={"q": "template/"})
        assert search_res.status_code == 200
        search_items = search_res.json()["items"]
        assert len(search_items) == 1
        assert search_items[0]["name"] == "TBM_양식.xlsx"
    finally:
        settings.document_explorer_base_dir = original_base_dir

