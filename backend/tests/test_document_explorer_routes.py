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

    samsung_dir = docs_dir / "\uc0bc\uc131\uad00\ub828 \uc591\uc2dd"
    samsung_dir.mkdir(parents=True, exist_ok=True)
    (samsung_dir / "tbm_template.hwp").write_text("dummy", encoding="utf-8")

    general_dir = docs_dir / "\uc77c\ubc18 \uc591\uc2dd" / "02-training"
    general_dir.mkdir(parents=True, exist_ok=True)
    (general_dir / "training_log.xlsx").write_text("dummy", encoding="utf-8")

    (docs_dir / "\uae30\ubcf8\uc591\uc2dd" / "\ud45c\uc9c0.ai").parent.mkdir(parents=True, exist_ok=True)
    (docs_dir / "\uae30\ubcf8\uc591\uc2dd" / "\ud45c\uc9c0.ai").write_text("dummy", encoding="utf-8")

    (field_dir / "instance_1_1710000000_field_doc.pdf").write_text("dummy", encoding="utf-8")
    (field_dir / "instance_1_1710000001_field_doc.xlsx").write_text("dummy", encoding="utf-8")
    (field_dir / "\ud604\uc7a5\uc81c\ucd9c_\uc0d8\ud50c.pdf").write_text("dummy", encoding="utf-8")

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
        by_name = {item["name"]: item for item in items}
        assert by_name["tbm_template.hwp"]["category"] == "template"
        assert by_name["training_log.xlsx"]["category"] == "general"
        assert by_name["field_doc.pdf"]["category"] == "field"
        assert by_name["field_doc.xlsx"]["category"] == "field"
        assert "instance_1_1710000000_field_doc.pdf" not in by_name
        assert "\ud45c\uc9c0.ai" not in by_name

        search_res = client.get("/document-explorer/search", params={"q": "tbm"})
        assert search_res.status_code == 200
        search_items = search_res.json()["items"]
        assert len(search_items) == 1
        assert search_items[0]["name"] == "tbm_template.hwp"

        field_xlsx = client.get(
            "/document-explorer/file",
            params={"relative_path": "field/instance_1_1710000001_field_doc.xlsx", "disposition": "attachment"},
        )
        assert field_xlsx.status_code == 200
    finally:
        settings.document_explorer_base_dir = original_base_dir
        settings.storage_root = original_storage_root


def test_document_explorer_field_download_falls_back_to_legacy_flat(tmp_path: Path):
    storage_root = tmp_path / "storage"
    field_dir = storage_root / "documents"
    field_dir.mkdir(parents=True, exist_ok=True)
    legacy = field_dir / "instance_3_1710000000_TBM_SITE.pdf"
    legacy.write_text("legacy-tbm", encoding="utf-8")

    original_storage_root = settings.storage_root
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
        res = client.get(
            "/document-explorer/file",
            params={
                "relative_path": "field/by_instance/3/TBM_SITE.pdf",
                "disposition": "attachment",
            },
        )
        assert res.status_code == 200
        assert res.content == b"legacy-tbm"
    finally:
        settings.storage_root = original_storage_root


def test_document_explorer_download_uses_display_filename(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    storage_root = tmp_path / "storage"
    field_dir = storage_root / "documents"
    field_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    disk = field_dir / "instance_2_999_field.pdf"
    disk.write_text("dummy", encoding="utf-8")

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
        res = client.get(
            "/document-explorer/file",
            params={"relative_path": "field/instance_2_999_field.pdf", "disposition": "attachment"},
        )
        assert res.status_code == 200
        assert "field.pdf" in res.headers.get("content-disposition", "")
    finally:
        settings.document_explorer_base_dir = original_base_dir
        settings.storage_root = original_storage_root


def test_document_explorer_list_allows_site_role(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    storage_root = tmp_path / "storage"
    field_dir = storage_root / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    field_dir.mkdir(parents=True, exist_ok=True)
    general_root = docs_dir / "\uc77c\ubc18 \uc591\uc2dd"
    general_root.mkdir(parents=True, exist_ok=True)
    (general_root / "site_visible.txt").write_text("ok", encoding="utf-8")
    (general_root / "nested" / "older_form.hwp").parent.mkdir(parents=True, exist_ok=True)
    (general_root / "nested" / "older_form.hwp").write_text("hwp", encoding="utf-8")
    legacy_samsung = docs_dir / "\uc0bc\uc131\uc778\uc815\uc81c"
    legacy_samsung.mkdir(parents=True, exist_ok=True)
    (legacy_samsung / "legacy_dup.hwp").write_text("legacy", encoding="utf-8")
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
        assert names == {"site_visible.txt", "older_form.hwp", "yesterday.txt", "today_tbm.hwp"}
        assert "legacy_dup.hwp" not in names
    finally:
        settings.document_explorer_base_dir = original_base_dir
        settings.storage_root = original_storage_root


def test_document_explorer_list_allows_site_manager_role(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    storage_root = tmp_path / "storage"
    general_root = docs_dir / "일반 양식"
    general_root.mkdir(parents=True, exist_ok=True)
    (general_root / "manager-visible.txt").write_text("ok", encoding="utf-8")

    original_base_dir = settings.document_explorer_base_dir
    original_storage_root = settings.storage_root
    settings.document_explorer_base_dir = docs_dir
    settings.storage_root = storage_root
    app = FastAPI()
    app.include_router(document_explorer_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=10,
        role=Role.SITE_FUNCTIONAL_EVAL,
        login_id="site-manager",
        site_id=1,
        ui_type="SITE",
    )

    try:
        response = TestClient(app).get("/document-explorer/list")
        assert response.status_code == 200
        assert response.json()["items"][0]["name"] == "manager-visible.txt"
    finally:
        settings.document_explorer_base_dir = original_base_dir
        settings.storage_root = original_storage_root


def test_document_explorer_searches_indexed_file_content(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    storage_root = tmp_path / "storage"
    general_root = docs_dir / "일반 양식"
    general_root.mkdir(parents=True, exist_ok=True)
    (general_root / "작업계획서.txt").write_text(
        "밀폐공간 작업 전 산소농도와 유해가스 농도를 측정한다.",
        encoding="utf-8",
    )

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
        response = client.get(
            "/document-explorer/search",
            params={"q": "산소농도 유해가스"},
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "작업계획서.txt"
        assert items[0]["match_source"] == "content"
        assert "산소농도" in items[0]["snippet"]
        assert items[0]["index_status"] == "indexed"
        assert items[0]["relevance"] > 0
    finally:
        settings.document_explorer_base_dir = original_base_dir
        settings.storage_root = original_storage_root


def test_document_explorer_file_open_and_not_found(tmp_path: Path):
    docs_dir = tmp_path / "docs" / "base"
    docs_dir.mkdir(parents=True, exist_ok=True)
    template_dir = docs_dir / "\uc0bc\uc131\uad00\ub828 \uc591\uc2dd"
    template_dir.mkdir(parents=True, exist_ok=True)
    file_path = template_dir / "tbm_template.hwp"
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
        rel = f"base/{template_dir.relative_to(docs_dir).as_posix()}/tbm_template.hwp"
        ok_res = client.get(
            "/document-explorer/file",
            params={"relative_path": rel, "disposition": "attachment"},
        )
        assert ok_res.status_code == 200
        assert "content-disposition" in {k.lower() for k in ok_res.headers.keys()}

        (docs_dir / "template" / "sheet.xlsx").parent.mkdir(parents=True, exist_ok=True)
        (docs_dir / "template" / "sheet.xlsx").write_text("xlsx-dummy", encoding="utf-8")
        ok_xlsx = client.get(
            "/document-explorer/file",
            params={"relative_path": "base/template/sheet.xlsx", "disposition": "inline"},
        )
        assert ok_xlsx.status_code == 200

        nf_res = client.get(
            "/document-explorer/file",
            params={"relative_path": f"{rel.rsplit('/', 1)[0]}/not-exists.hwp", "disposition": "attachment"},
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
        upload_rel = "\uc77c\ubc18 \uc591\uc2dd/std-forms/a.xlsx"
        r1 = client.post(
            "/document-explorer/upload",
            data={"relative_path": upload_rel},
            files={"file": ("a.xlsx", b"v1", "application/octet-stream")},
        )
        assert r1.status_code == 200
        assert (docs_dir / "\uc77c\ubc18 \uc591\uc2dd" / "std-forms" / "a.xlsx").read_bytes() == b"v1"

        r2 = client.post(
            "/document-explorer/upload",
            data={"relative_path": upload_rel},
            files={"file": ("a.xlsx", b"v2-updated", "application/octet-stream")},
        )
        assert r2.status_code == 200
        assert (docs_dir / "\uc77c\ubc18 \uc591\uc2dd" / "std-forms" / "a.xlsx").read_bytes() == b"v2-updated"
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
