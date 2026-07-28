from __future__ import annotations

from datetime import date
from io import BytesIO
from types import SimpleNamespace
import asyncio
import base64
import hashlib
import zipfile

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.core.enums import Role
from app.modules.coupang_mvp import routes
from app.modules.coupang_mvp import xlsx_export
from app.modules.coupang_mvp.schemas import CoupangDocumentUpsert


def _user(login_id: str = "안전보건-정상익"):
    return SimpleNamespace(
        id=48,
        name="쿠팡 현장관리자",
        login_id=login_id,
        role=Role.HQ_SAFE,
        site_id=None,
    )


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(routes.settings, "storage_root", tmp_path)
    yield tmp_path


def test_document_round_trip_is_scoped_to_coupang_site(isolated_storage):
    payload = CoupangDocumentUpsert(
        title="4층 일일 작업계획",
        work_date=date(2026, 7, 28),
        floor="4F",
        workplace="지하1층 2번코어",
        work_description="케이블 포설",
        drawing={
            "width": 1600,
            "height": 1000,
            "background_asset_id": None,
            "objects": [
                {
                    "id": "icon-1",
                    "type": "icon",
                    "x": 320,
                    "y": 240,
                    "w": 120,
                    "h": 120,
                    "label": "작업구역",
                    "color": "#dc2626",
                }
            ],
        },
    )

    created = routes.create_document(payload, _user())
    assert created["id"] == 1
    assert created["site_id"] == 101
    assert "YAN 5FC" in created["site_name"]
    assert created["contractor_name"] == "부현전기"
    assert created["drawing"]["objects"][0]["label"] == "작업구역"

    listed = routes.list_documents(_user())
    assert [item["id"] for item in listed["items"]] == [1]

    payload.notes = "관리감독자 확인 완료"
    updated = routes.update_document(1, payload, _user())
    assert updated["notes"] == "관리감독자 확인 완료"
    assert routes.get_document(1, _user())["drawing"] == payload.drawing


def test_non_coupang_site_is_rejected(isolated_storage):
    with pytest.raises(HTTPException) as exc_info:
        routes.access_info(_user("쿠팡양지-김민수"))
    assert exc_info.value.status_code == 403


def test_private_lab_returns_selectable_sites(isolated_storage):
    result = routes.access_info(_user())
    assert result["pilot_only"] is True
    assert {site["id"] for site in result["sites"]} == {46, 47, 48, 86, 89, 101}
    assert next(site for site in result["sites"] if site["id"] == 101)["template_ready"] is True


def test_image_asset_upload_and_read(isolated_storage):
    content = BytesIO()
    Image.new("RGB", (80, 60), "#ef4444").save(content, format="JPEG")
    upload = UploadFile(filename="현장사진.jpg", file=BytesIO(content.getvalue()), headers={"content-type": "image/jpeg"})

    result = asyncio.run(routes.upload_asset(_user(), upload))

    assert result["width"] == 80
    assert result["height"] == 60
    assert result["asset_id"]
    response = routes.get_asset(result["asset_id"], _user())
    assert str(response.path).endswith(".jpg")


def test_submission_workbook_preserves_package_and_replaces_drawing(tmp_path, monkeypatch):
    template = tmp_path / "template.xlsx"
    output = tmp_path / "output.xlsx"
    sheet_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="5"><c r="D5" t="inlineStr"><is><t>old</t></is></c></row>
    <row r="18"><c r="D18" t="inlineStr"><is><t>old</t></is></c></row>
    <row r="37"><c r="B37" t="inlineStr"><is><t>old</t></is></c><c r="C37" t="inlineStr"><is><t>old</t></is></c></row>
    <row r="53"><c r="F53" t="inlineStr"><is><t>old</t></is></c><c r="H53" t="inlineStr"><is><t>old</t></is></c></row>
  </sheetData>
</worksheet>"""
    workbook_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><calcPr/></workbook>"""
    with zipfile.ZipFile(template, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr("xl/worksheets/sheet2.xml", sheet_xml)
        archive.writestr("xl/media/image10.png", b"old-4f")
        archive.writestr("xl/media/image11.png", b"old-6f")
        archive.writestr("keep/original.bin", b"preserve-me")
    monkeypatch.setattr(
        xlsx_export,
        "_APPROVED_TEMPLATE_SHA256",
        hashlib.sha256(template.read_bytes()).hexdigest().upper(),
    )
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"drawing"
    drawing_png = "data:image/png;base64," + base64.b64encode(png_bytes).decode()

    xlsx_export.generate_submission_workbook(
        template,
        output,
        {
            "work_date": "2026-07-28",
            "floor": "4F",
            "workplace": "지하1층 2번코어",
            "work_description": "케이블 포설작업",
            "hazard": "안전고리 미체결로 인한 추락 위험",
            "control": "안전고리 체결 및 관리감독자 확인",
            "manager_name": "정상익",
            "worker_count": 5,
            "today_jobs": [
                {"floor": "4F", "workplace": "4층 2~3챔버", "description": "조명 행거 설치", "people": 3},
                {"floor": "6F", "workplace": "6층 1~4챔버", "description": "케이블 포설", "people": 2},
            ],
        },
        drawing_png,
    )

    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert archive.read("keep/original.bin") == b"preserve-me"
        assert archive.read("xl/media/image10.png") == png_bytes
        assert archive.read("xl/media/image11.png") == b"old-6f"
        daily_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "지하1층 2번코어" in daily_xml
        assert "안전고리 미체결로 인한 추락 위험" in daily_xml
        assert "4층 2~3챔버 조명 행거 설치" in daily_xml
        assert "6층 1~4챔버 케이블 포설" in daily_xml
