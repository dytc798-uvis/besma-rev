#!/usr/bin/env python3
"""Sync document explorer templates from Z: drives into docs/base."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = REPO_ROOT / "docs" / "base"
SAMSUNG_SRC = Path(
    r"Z:\4. 안전보건관리실\011 협력사 별 활동\삼성인정제_삼성물산\99. 현장 서류양식"
)
GENERAL_SRC = Path(r"Z:\4. 안전보건관리실\012 표준 양식 (넘버링 전)\현장 안전서류양식")
SAMSUNG_DEST = BASE_DIR / "삼성관련 양식"
GENERAL_DEST = BASE_DIR / "일반 양식"
LEGACY_SAMSUNG = BASE_DIR / "삼성인정제"
LEGACY_GENERAL = BASE_DIR / "현장 안전서류양식"

SKIP_SUFFIXES = {".zip"}


def copy_if_newer(src: Path, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(src, dest)
        return "added"
    src_mtime = src.stat().st_mtime
    dest_mtime = dest.stat().st_mtime
    if src_mtime > dest_mtime:
        shutil.copy2(src, dest)
        return "updated"
    return "skipped"


def sync_tree(src_root: Path, dest_root: Path, *, skip_zip: bool = False) -> dict[str, int]:
    stats = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}
    if not src_root.exists():
        print(f"missing source: {src_root}")
        return stats
    for src in sorted(src_root.rglob("*")):
        if not src.is_file():
            continue
        if skip_zip and src.suffix.lower() in SKIP_SUFFIXES:
            continue
        rel = src.relative_to(src_root)
        dest = dest_root / rel
        try:
            result = copy_if_newer(src, dest)
            stats[result] += 1
            if dest_root == SAMSUNG_DEST and result != "skipped":
                print(f"  {result}: {rel.as_posix()}")
        except OSError as exc:
            stats["errors"] += 1
            print(f"  error: {rel.as_posix()} ({exc})")
    return stats


def merge_stats(total: dict[str, int], part: dict[str, int]) -> None:
    for key, value in part.items():
        total[key] = total.get(key, 0) + value


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    totals: dict[str, int] = {}
    print("sync samsung templates")
    merge_stats(totals, sync_tree(SAMSUNG_SRC, SAMSUNG_DEST, skip_zip=True))
    print("sync general templates")
    merge_stats(totals, sync_tree(GENERAL_SRC, GENERAL_DEST))
    if LEGACY_SAMSUNG.exists():
        print("migrate legacy samsung folder")
        merge_stats(totals, sync_tree(LEGACY_SAMSUNG, SAMSUNG_DEST))
    if LEGACY_GENERAL.exists():
        print("migrate legacy general folder")
        merge_stats(totals, sync_tree(LEGACY_GENERAL, GENERAL_DEST))
    for legacy_dir in (LEGACY_SAMSUNG, LEGACY_GENERAL):
        if legacy_dir.exists():
            shutil.rmtree(legacy_dir)
            print(f"removed legacy folder: {legacy_dir.name}")
    print(
        "done",
        f"added={totals.get('added', 0)}",
        f"updated={totals.get('updated', 0)}",
        f"skipped={totals.get('skipped', 0)}",
        f"errors={totals.get('errors', 0)}",
        f"at={datetime.now(timezone.utc).isoformat()}",
    )


if __name__ == "__main__":
    main()
