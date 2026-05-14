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
    (field_dir / "현장제출_샘플.pdf").write_text("dummy", encoding="utf-8")

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
        assert len(items) == 6
        names = {item["name"] for item in items}
        assert "현장안전일지.pdf" in names
        assert "TBM_양식.xlsx" in names
        assert "제출_안전일지.hwp" in names
        assert "표지.ai" in names
        assert "현장제출_샘플.pdf" in names
        assert "instance_1_1710000000_일일서류.xlsx" in names

        search_res = client.get("/document-explorer/search", params={"q": "현장안전일지"})
        assert search_res.status_code == 200
        search_items = search_res.json()["items"]
        assert len(search_items) == 1
        assert search_items[0]["name"] == "현장안전일지.pdf"

        search_tbm = client.get("/document-explorer/search", params={"q": "TBM"})
        assert search_tbm.status_code == 200
        tbm_names = {item["name"] for item in search_tbm.json()["items"]}
        assert "TBM_양식.xlsx" in tbm_names

        field_xlsx = client.get(
            "/document-explorer/file",
            params={"relative_path": "field/instance_1_1710000000_일일서류.xlsx", "disposition": "attachment"},
        )
        assert field_xlsx.status_code == 200
    finally:
        settings.document_explorer_base_dir = original_base_dir
        settings.storage_root = original_storage_root


def test_document_explorer_list_allows_site_role(tmp_path: Path):
    """현장(SITE) 계정도 HQ와 동일하게 base+field 전체 스캔 목록을 본다(역할별 부분집합 없음)."""
    docs_dir = tmp_path / "docs" / "base"
    storage_root = tmp_path / "storage"
    field_dir = storage_root / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    field_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "site_visible.txt").write_text("ok", encoding="utf-8")
    (docs_dir / "nested" / "older_form.hwp").parent.mkdir(parents=True, exist_ok=True)
    (docs_dir / "nested" / "older_form.hwp").write_text("hwp", encoding="utf-8")
    (field_dir / "instance_1_1710000000_yesterday.txt").write_text("old", encoding="utf-8")
    (field_dir / "instance_1_1999999999_today_tbm.hwp").write_text("tbm", encoding="utf-8")

    original_base_dir = settings.document_explorer_base_dir
    original_storage_root = settings.storage_root
    settings.document_explorer_base_dir = docs_dir
    settings.storage_root = storage_root

    app = FastAPI()
    app.include_router(document_explorer_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=9,
        role=Role.SITE,
        login_id="site02",
        site_id=1,
        ui_type="SITE",
    )
    client = TestClient(app)

    try:
        res = client.get("/document-explorer/list")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 4
        names = {item["name"] for item in items}
        assert names == {"site_visible.txt", "older_form.hwp", "instance_1_1710000000_yesterday.txt", "instance_1_1999999999_today_tbm.hwp"}
        paths = {item["relative_path"] for item in items}
        assert "base/site_visible.txt" in paths
        assert "base/nested/older_form.hwp" in paths
        assert "field/instance_1_1710000000_yesterday.txt" in paths
        assert "field/instance_1_1999999999_today_tbm.hwp" in paths
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

        (docs_dir / "template" / "sheet.xlsx").write_text("xlsx-dummy", encoding="utf-8")
        ok_xlsx = client.get(
            "/document-explorer/file",
            params={"relative_path": "base/template/sheet.xlsx", "disposition": "inline"},
        )
        assert ok_xlsx.status_code == 200

        nf_res = client.get(
            "/document-explorer/file",
            params={"relative_path": "base/template/not-exists.xlsx", "disposition": "inline"},
        )
        assert nf_res.status_code == 404
    finally:
        settings.document_explorer_base_dir = original_base_dir


def test_document_explorer_upload_overwrite(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    docs_dir.mkdir(parents=True, exist_ok=True)
    original_base_dir = settings.document_explorer_base_dir
    settings.document_explorer_base_dir = docs_dir

    app = FastAPI()
    app.include_router(document_explorer_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.HQ_SAFE_ADMIN,
        login_id="admin",
        ui_type="HQ_SAFE",
    )
    client = TestClient(app)

    try:
        r1 = client.post(
            "/document-explorer/upload",
            data={"relative_path": "std-forms/a.xlsx"},
            files={"file": ("a.xlsx", b"v1", "application/octet-stream")},
        )
        assert r1.status_code == 200
        assert (docs_dir / "std-forms" / "a.xlsx").read_bytes() == b"v1"

        r2 = client.post(
            "/document-explorer/upload",
            data={"relative_path": "std-forms/a.xlsx"},
            files={"file": ("a.xlsx", b"v2-updated", "application/octet-stream")},
        )
        assert r2.status_code == 200
        assert (docs_dir / "std-forms" / "a.xlsx").read_bytes() == b"v2-updated"
    finally:
        settings.document_explorer_base_dir = original_base_dir


def test_document_explorer_upload_site_forbidden(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    docs_dir.mkdir(parents=True, exist_ok=True)
    original_base_dir = settings.document_explorer_base_dir
    settings.document_explorer_base_dir = docs_dir

    app = FastAPI()
    app.include_router(document_explorer_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=2,
        role=Role.SITE,
        login_id="site01",
        site_id=1,
        ui_type="SITE",
    )
    client = TestClient(app)

    try:
        res = client.post(
            "/document-explorer/upload",
            data={"relative_path": "x.txt"},
            files={"file": ("x.txt", b"hi", "text/plain")},
        )
        assert res.status_code == 403
    finally:
        settings.document_explorer_base_dir = original_base_dir


def test_document_explorer_upload_hq_demo_readonly(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    docs_dir.mkdir(parents=True, exist_ok=True)
    original_base_dir = settings.document_explorer_base_dir
    settings.document_explorer_base_dir = docs_dir

    app = FastAPI()
    app.include_router(document_explorer_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=3,
        role=Role.HQ_SAFE,
        login_id="hq01",
        ui_type="HQ_SAFE",
    )
    client = TestClient(app)

    try:
        res = client.post(
            "/document-explorer/upload",
            data={"relative_path": "x.txt"},
            files={"file": ("x.txt", b"hi", "text/plain")},
        )
        assert res.status_code == 403
    finally:
        settings.document_explorer_base_dir = original_base_dir


def test_document_explorer_upload_path_traversal_rejected(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    docs_dir.mkdir(parents=True, exist_ok=True)
    original_base_dir = settings.document_explorer_base_dir
    settings.document_explorer_base_dir = docs_dir

    app = FastAPI()
    app.include_router(document_explorer_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.HQ_SAFE,
        login_id="hq-safe-real",
        ui_type="HQ_SAFE",
    )
    client = TestClient(app)

    try:
        res = client.post(
            "/document-explorer/upload",
            data={"relative_path": "../evil.txt"},
            files={"file": ("evil.txt", b"x", "text/plain")},
        )
        assert res.status_code == 400
    finally:
        settings.document_explorer_base_dir = original_base_dir

