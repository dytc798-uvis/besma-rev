from __future__ import annotations

import asyncio
import io
import json
import zipfile
from types import SimpleNamespace

from fastapi import UploadFile

from app.core.enums import Role
from app.modules.field_form_uploads import routes


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("form.txt", "field form")
    return buffer.getvalue()


def test_field_form_upload_deadline_is_unlimited() -> None:
    payload = routes.get_deadline()

    assert payload["deadline"] is None
    assert payload["upload_open"] is True
    assert payload["max_uploads_per_site"] == 2


def test_site_can_upload_without_a_date_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "storage_root", tmp_path)
    current_user = SimpleNamespace(
        id=390,
        name="장천식",
        login_id="현대산업시티오씨-장천식",
        role=Role.SITE_FUNCTIONAL_EVAL,
        site_id=113,
        site=SimpleNamespace(site_name="시티오씨엘 8단지"),
    )
    upload = UploadFile(filename="forms.zip", file=io.BytesIO(_zip_bytes()))

    row = asyncio.run(routes.upload_field_forms(current_user=current_user, file=upload))

    assert row["site_id"] == 113
    assert row["document_count"] == 1
    assert (tmp_path / row["stored_path"]).is_file()
    ledger = json.loads((tmp_path / "field-form-uploads" / "ledger.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in ledger] == [row["id"]]
