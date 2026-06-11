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


def instance_id_from_storage_relative_path(relative_path: str) -> int | None:
    """storage_root 기준 상대경로에서 instance_id 추출(by_instance·legacy flat)."""
    rel = (relative_path or "").replace("\\", "/").strip()
    if not rel:
        return None
    parts = [p for p in rel.split("/") if p]
    if BY_INSTANCE_DIR in parts:
        idx = parts.index(BY_INSTANCE_DIR)
        if idx + 1 < len(parts):
            try:
                return int(parts[idx + 1])
            except ValueError:
                return None
    legacy = _LEGACY_FIELD_DISK_NAME_RE.match(Path(rel).name)
    if legacy:
        return int(legacy.group("instance_id"))
    return None


def _legacy_flat_paths_on_disk(
    storage_root: Path,
    *,
    instance_id: int,
    file_name: str | None,
    disk_name: str,
) -> list[Path]:
    """DB는 by_instance인데 디스크만 legacy flat에 남은 경우(과거 업로드) 탐색."""
    docs_dir = documents_root(storage_root)
    if not docs_dir.is_dir():
        return []

    names: list[str] = []
    if file_name:
        names.append(file_name)
        names.append(versioned_primary_filename(file_name, 1))
    legacy = _LEGACY_FIELD_DISK_NAME_RE.match(disk_name)
    if legacy:
        label = legacy.group("label")
        if label not in names:
            names.append(label)
        version = legacy.group("version")
        if version:
            vname = versioned_primary_filename(label, int(version))
            if vname not in names:
                names.append(vname)

    found: list[Path] = []
    seen: set[str] = set()
    for name in names:
        for path in sorted(docs_dir.glob(f"instance_{instance_id}_*_{name}")):
            key = path.as_posix()
            if path.is_file() and key not in seen:
                seen.add(key)
                found.append(path)
    return found


def resolve_existing_storage_path(
    storage_root: Path,
    relative_path: str,
    *,
    instance_id: int | None = None,
    file_name: str | None = None,
    version_no: int | None = None,
) -> Path | None:
    """DB에 저장된 상대경로 → 디스크에 존재하는 파일 Path (legacy flat ↔ by_instance 양방향)."""
    rel = (relative_path or "").strip()
    if not rel:
        return None

    direct = storage_root / rel
    if direct.is_file():
        return direct

    disk_name = Path(rel).name
    resolved_instance_id = instance_id if instance_id is not None else instance_id_from_storage_relative_path(rel)
    candidates: list[str] = []

    if resolved_instance_id is not None:
        migrated = legacy_disk_name_to_target_relative(
            instance_id=resolved_instance_id,
            disk_name=disk_name,
            file_name=file_name,
            version_no=version_no,
        )
        if migrated:
            candidates.append(migrated)

        deriv = legacy_derivative_to_target_relative(instance_id=resolved_instance_id, disk_name=disk_name)
        if deriv:
            candidates.append(deriv)

        if file_name and BY_INSTANCE_DIR not in rel.replace("\\", "/"):
            candidates.append(
                f"{instance_dir_relative(resolved_instance_id)}/{versioned_primary_filename(file_name, version_no or 1)}"
            )

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        path = storage_root / candidate
        if path.is_file():
            return path

    if resolved_instance_id is not None:
        for legacy_path in _legacy_flat_paths_on_disk(
            storage_root,
            instance_id=resolved_instance_id,
            file_name=file_name,
            disk_name=disk_name,
        ):
            return legacy_path

    return None


def is_storage_path_available(
    storage_root: Path,
    relative_path: str | None,
    *,
    instance_id: int | None = None,
    file_name: str | None = None,
    version_no: int | None = None,
) -> bool:
    """DB file_path가 있어도 실제 파일이 없으면 False (다운로드 버튼 노출 판단용)."""
    return resolve_existing_storage_path(
        storage_root,
        relative_path or "",
        instance_id=instance_id,
        file_name=file_name,
        version_no=version_no,
    ) is not None
