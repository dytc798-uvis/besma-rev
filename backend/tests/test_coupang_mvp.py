from __future__ import annotations

from datetime import date
from io import BytesIO
from types import SimpleNamespace
import asyncio

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.core.enums import Role
from app.modules.coupang_mvp import routes
from app.modules.coupang_mvp.schemas import CoupangDocumentUpsert


def _user(site_name: str = "[3.쿠팡] INC 46FC(인천) 전기공사", client_name: str = "쿠팡"):
    return SimpleNamespace(
        id=48,
        name="쿠팡 현장관리자",
        login_id="coupang_manager",
        role=Role.SITE,
        site_id=48,
        site=SimpleNamespace(
            site_name=site_name,
            client_name=client_name,
            contractor_name="",
            description="",
        ),
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
        routes.access_info(_user("일반 공동주택 현장", "일반 발주처"))
    assert exc_info.value.status_code == 403


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
