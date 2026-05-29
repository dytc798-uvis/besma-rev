#!/usr/bin/env python3
"""Migrate storage/documents from flat instance_* files to documents/by_instance/{id}/."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config.settings import settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.documents.models import Document  # noqa: E402
from app.modules.documents.storage_paths import (  # noqa: E402
    BY_INSTANCE_DIR,
    documents_root,
    field_file_display_name,
    is_field_derivative_filename,
    legacy_derivative_to_target_relative,
    legacy_disk_name_to_target_relative,
    versioned_primary_filename,
)


def _migrate_path(
    storage_root: Path,
    *,
    old_rel: str | None,
    instance_id: int,
    file_name: str | None,
    version_no: int | None,
    dry_run: bool,
) -> str | None:
    if not old_rel:
        return None
    normalized = old_rel.replace("\\", "/")
    if f"/{BY_INSTANCE_DIR}/" in normalized:
        return normalized

    old_path = storage_root / normalized
    if not old_path.exists():
        return None

    disk_name = old_path.name
    if is_field_derivative_filename(disk_name):
        new_rel = legacy_derivative_to_target_relative(instance_id=instance_id, disk_name=disk_name)
    else:
        new_rel = legacy_disk_name_to_target_relative(
            instance_id=instance_id,
            disk_name=disk_name,
            file_name=file_name,
            version_no=version_no,
        )
    if not new_rel:
        return None

    new_path = storage_root / new_rel
    if new_path.resolve() == old_path.resolve():
        return normalized

    if new_path.exists() and new_path.resolve() != old_path.resolve():
        print(f"  skip (target exists): {new_rel}")
        return normalized

    print(f"  move: {normalized} -> {new_rel}")
    if not dry_run:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
    return new_rel


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="실제 이동·DB 갱신·고아 삭제 수행")
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        help="DB에 없는 legacy instance_* 파일 삭제 (--apply 필요)",
    )
    args = parser.parse_args()
    dry_run = not args.apply

    storage_root = settings.storage_root.resolve()
    docs_dir = documents_root(storage_root)
    if not docs_dir.exists():
        print(f"documents dir missing: {docs_dir}")
        return 0

    init_db()
    db = SessionLocal()
    referenced: set[str] = set()
    moved = 0
    try:
        docs = (
            db.query(Document)
            .filter(Document.instance_id.isnot(None), Document.file_path.isnot(None))
            .all()
        )
        print(f"documents with instance: {len(docs)} (dry_run={dry_run})")
        for doc in docs:
            inst_id = int(doc.instance_id)
            print(f"doc#{doc.id} instance={inst_id} file_name={doc.file_name!r}")
            for attr in ("file_path", "original_file_path", "optimized_file_path"):
                old_rel = getattr(doc, attr)
                new_rel = _migrate_path(
                    storage_root,
                    old_rel=old_rel,
                    instance_id=inst_id,
                    file_name=doc.file_name,
                    version_no=doc.version_no,
                    dry_run=dry_run,
                )
                if new_rel:
                    referenced.add(new_rel.replace("\\", "/"))
                    if old_rel and new_rel != old_rel.replace("\\", "/"):
                        moved += 1
                        if not dry_run:
                            setattr(doc, attr, new_rel)
            if not dry_run:
                db.add(doc)
        if not dry_run:
            db.commit()
    finally:
        db.close()

    orphan_deleted = 0
    if args.delete_orphans:
        for path in sorted(docs_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(storage_root)).replace("\\", "/")
            if rel in referenced:
                continue
            name = path.name
            if name.startswith("instance_") or is_field_derivative_filename(name):
                print(f"  delete orphan: {rel}")
                if not dry_run:
                    path.unlink(missing_ok=True)
                orphan_deleted += 1

    print(f"done moved_fields={moved} orphan_deleted={orphan_deleted} dry_run={dry_run}")
    if dry_run:
        print("Re-run with --apply to execute. Add --delete-orphans to remove unreferenced legacy files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
