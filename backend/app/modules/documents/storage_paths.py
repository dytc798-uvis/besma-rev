"""현장 제출 문서 storage 경로·표시 이름 규칙."""

from __future__ import annotations

import re
from pathlib import Path

from app.config.settings import settings

BY_INSTANCE_DIR = "by_instance"

# legacy: instance_{id}_{epoch}[_v{n}]_{human_label}
_LEGACY_FIELD_DISK_NAME_RE = re.compile(
    r"^instance_(?P<instance_id>\d+)_(?P<ts>\d+)(?:_v(?P<version>\d+))?_(?P<label>.+)$",
    re.IGNORECASE,
)
# by_instance/{id}/v{n}_{human_label}
_VERSIONED_FIELD_DISK_NAME_RE = re.compile(
    r"^v(?P<version>\d+)_(?P<label>.+)$",
    re.IGNORECASE,
)


def documents_root(storage_root: Path | None = None) -> Path:
    root = storage_root or settings.storage_root
    return root / settings.documents_dir_name


def instance_dir_relative(instance_id: int) -> str:
    return f"{settings.documents_dir_name}/{BY_INSTANCE_DIR}/{instance_id}"


def ensure_instance_dir(storage_dir: Path, instance_id: int) -> Path:
    inst_dir = storage_dir / BY_INSTANCE_DIR / str(instance_id)
    inst_dir.mkdir(parents=True, exist_ok=True)
    return inst_dir


def versioned_primary_filename(safe_name: str, version_no: int) -> str:
    if version_no <= 1:
        return safe_name
    return f"v{version_no}_{safe_name}"


def image_derivative_filenames(safe_name: str, original_ext: str, optimized_ext: str) -> tuple[str, str]:
    stem = Path(safe_name).stem
    return (
        f"{stem}__original{original_ext}",
        f"{stem}__optimized{optimized_ext}",
    )


def write_instance_file(storage_dir: Path, instance_id: int, filename: str, content: bytes) -> str:
    inst_dir = ensure_instance_dir(storage_dir, instance_id)
    target = inst_dir / filename
    target.write_bytes(content)
    return target.relative_to(settings.storage_root).as_posix()


def field_file_display_name(disk_name: str) -> str:
    """탐색·다운로드에 쓸 사람이 읽는 파일명."""
    legacy = _LEGACY_FIELD_DISK_NAME_RE.match(disk_name)
    if legacy:
        label = legacy.group("label")
        version = legacy.group("version")
        if not version:
            return label
        path = Path(label)
        return f"{path.stem} (v{version}){path.suffix}"

    versioned = _VERSIONED_FIELD_DISK_NAME_RE.match(disk_name)
    if versioned:
        label = versioned.group("label")
        version = versioned.group("version")
        path = Path(label)
        return f"{path.stem} (v{version}){path.suffix}"

    return disk_name


def is_field_derivative_filename(name: str) -> bool:
    lower = name.lower()
    return "__original" in lower or "__optimized" in lower


def legacy_disk_name_to_target_relative(
    *,
    instance_id: int,
    disk_name: str,
    file_name: str | None,
    version_no: int | None,
) -> str | None:
    """legacy flat instance_* 파일 → by_instance/{id}/... 상대경로."""
    label = file_name
    version = version_no or 1
    match = _LEGACY_FIELD_DISK_NAME_RE.match(disk_name)
    if match:
        label = label or match.group("label")
        if match.group("version"):
            version = int(match.group("version"))
    if not label:
        return None
    filename = versioned_primary_filename(label, version)
    return f"{instance_dir_relative(instance_id)}/{filename}"


_LEGACY_DERIVATIVE_DISK_NAME_RE = re.compile(
    r"^instance_(?P<instance_id>\d+)_(?P<ts>\d+)(?:_v(?P<version>\d+))?_(?P<stem>.+?)(?P<kind>__original|__optimized)(?P<ext>\.[^.]+)$",
    re.IGNORECASE,
)


def legacy_derivative_to_target_relative(*, instance_id: int, disk_name: str) -> str | None:
    match = _LEGACY_DERIVATIVE_DISK_NAME_RE.match(disk_name)
    if not match:
        return None
    new_name = f"{match.group('stem')}{match.group('kind')}{match.group('ext')}"
    return f"{instance_dir_relative(instance_id)}/{new_name}"


def resolve_existing_storage_path(
    storage_root: Path,
    relative_path: str,
    *,
    instance_id: int | None = None,
    file_name: str | None = None,
    version_no: int | None = None,
) -> Path | None:
    """DB에 저장된 상대경로 → 디스크에 존재하는 파일 Path (legacy flat → by_instance 포함)."""
    rel = (relative_path or "").strip()
    if not rel:
        return None

    direct = storage_root / rel
    if direct.is_file():
        return direct

    disk_name = Path(rel).name
    candidates: list[str] = []

    if instance_id is not None:
        migrated = legacy_disk_name_to_target_relative(
            instance_id=instance_id,
            disk_name=disk_name,
            file_name=file_name,
            version_no=version_no,
        )
        if migrated:
            candidates.append(migrated)

        deriv = legacy_derivative_to_target_relative(instance_id=instance_id, disk_name=disk_name)
        if deriv:
            candidates.append(deriv)

        if file_name and BY_INSTANCE_DIR not in rel.replace("\\", "/"):
            candidates.append(
                f"{instance_dir_relative(instance_id)}/{versioned_primary_filename(file_name, version_no or 1)}"
            )

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        path = storage_root / candidate
        if path.is_file():
            return path

    return None
