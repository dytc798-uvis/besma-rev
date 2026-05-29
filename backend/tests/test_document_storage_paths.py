from __future__ import annotations

from app.config.settings import settings
from app.modules.documents.storage_paths import (
    field_file_display_name,
    is_field_derivative_filename,
    legacy_disk_name_to_target_relative,
    versioned_primary_filename,
    write_instance_file,
)


def test_field_file_display_name_legacy_and_versioned():
    assert field_file_display_name("instance_157_1779435887_일일안전일지.txt") == "일일안전일지.txt"
    assert field_file_display_name("instance_9_1_v2_TBM.hwp") == "TBM (v2).hwp"
    assert field_file_display_name("v3_TBM.hwp") == "TBM (v3).hwp"
    assert field_file_display_name("일일안전일지.txt") == "일일안전일지.txt"


def test_legacy_disk_name_to_target_relative():
    rel = legacy_disk_name_to_target_relative(
        instance_id=157,
        disk_name="instance_157_1779435887_일일안전일지.txt",
        file_name="일일안전일지.txt",
        version_no=1,
    )
    assert rel == "documents/by_instance/157/일일안전일지.txt"


def test_write_instance_file(tmp_path):
    storage_root = tmp_path
    original_storage_root = settings.storage_root
    settings.storage_root = storage_root
    try:
        docs_dir = storage_root / settings.documents_dir_name
        rel = write_instance_file(docs_dir, 5, "TBM_SITE.pdf", b"pdf")
        assert rel == "documents/by_instance/5/TBM_SITE.pdf"
        assert (storage_root / rel).read_bytes() == b"pdf"
    finally:
        settings.storage_root = original_storage_root


def test_versioned_primary_filename():
    assert versioned_primary_filename("a.pdf", 1) == "a.pdf"
    assert versioned_primary_filename("a.pdf", 2) == "v2_a.pdf"


def test_is_field_derivative_filename():
    assert is_field_derivative_filename("x__original.jpg")
    assert not is_field_derivative_filename("TBM.pdf")
