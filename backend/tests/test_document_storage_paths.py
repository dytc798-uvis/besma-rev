from __future__ import annotations

from app.config.settings import settings
from app.modules.documents.storage_paths import (
    field_file_display_name,
    is_field_derivative_filename,
    is_storage_path_available,
    legacy_disk_name_to_target_relative,
    resolve_existing_storage_path,
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


def test_resolve_existing_storage_path_by_instance_db_with_legacy_flat_disk(tmp_path):
    """DB는 by_instance 경로인데 실제 파일만 legacy flat에 남은 과거 TBM 케이스."""
    storage_root = tmp_path
    original_storage_root = settings.storage_root
    settings.storage_root = storage_root
    try:
        docs_dir = storage_root / settings.documents_dir_name
        docs_dir.mkdir(parents=True, exist_ok=True)
        legacy = docs_dir / "instance_148_1779262223_TBM_C18BL_260609.hwp"
        legacy.write_bytes(b"past-tbm")
        db_rel = "documents/by_instance/148/TBM_C18BL_260609.hwp"
        resolved = resolve_existing_storage_path(
            storage_root,
            db_rel,
            instance_id=148,
            file_name="TBM_C18BL_260609.hwp",
            version_no=1,
        )
        assert resolved is not None
        assert resolved.read_bytes() == b"past-tbm"
        assert is_storage_path_available(
            storage_root,
            db_rel,
            instance_id=148,
            file_name="TBM_C18BL_260609.hwp",
            version_no=1,
        )
    finally:
        settings.storage_root = original_storage_root


def test_resolve_existing_storage_path_legacy_to_by_instance(tmp_path):
    storage_root = tmp_path
    original_storage_root = settings.storage_root
    settings.storage_root = storage_root
    try:
        rel = write_instance_file(
            storage_root / settings.documents_dir_name,
            148,
            "일일안전회의일지_24025_260520.pdf",
            b"pdf-by-instance",
        )
        legacy = "documents/instance_148_1779262223_일일안전회의일지_24025_260520.pdf"
        resolved = resolve_existing_storage_path(
            storage_root,
            legacy,
            instance_id=148,
            file_name="일일안전회의일지_24025_260520.pdf",
            version_no=1,
        )
        assert resolved is not None
        assert resolved.relative_to(storage_root).as_posix() == rel
        assert resolved.read_bytes() == b"pdf-by-instance"
    finally:
        settings.storage_root = original_storage_root
