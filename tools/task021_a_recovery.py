#!/usr/bin/env python3
"""TASK 021 A-grade file-name normalization tool.

The default mode is read-only.  The tool only renames the single verified
physical candidate to the already-normalized DB file_path.  It never deletes
files and it refuses to run when the frozen target set is not exactly 274 rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_COUNT = 274
EXCLUDED_IDS = {27, 300, 366}
MAGIC = {
    ".pdf": (b"%PDF",),
    ".xlsx": (b"PK\x03\x04",),
    ".docx": (b"PK\x03\x04",),
    ".hwp": (b"\xd0\xcf\x11\xe0", b"PK\x03\x04"),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def has_control(value: str) -> bool:
    return any(unicodedata.category(ch).startswith("C") for ch in value)


def safe_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError("absolute_or_empty_path")
    result = (root / Path(relative)).resolve()
    try:
        result.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("path_escape") from exc
    return result


def load_targets(mapping_path: Path) -> list[dict]:
    payload = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
    rows = [
        row
        for row in payload.get("documents", [])
        if row.get("grade") == "A" and int(row.get("document_id", -1)) not in EXCLUDED_IDS
    ]
    ids = [int(row["document_id"]) for row in rows]
    if len(rows) != EXPECTED_COUNT or len(set(ids)) != EXPECTED_COUNT:
        raise RuntimeError(
            f"frozen target count mismatch: rows={len(rows)}, unique_ids={len(set(ids))}, "
            f"expected={EXPECTED_COUNT}"
        )
    if set(ids) & EXCLUDED_IDS:
        raise RuntimeError("excluded ID found in target set")
    return sorted(rows, key=lambda row: int(row["document_id"]))


def magic_matches(path: Path) -> bool:
    expected = MAGIC.get(path.suffix.lower())
    if expected is None:
        return True
    head = path.read_bytes()[:16]
    return any(head.startswith(value) for value in expected)


def inspect(db: sqlite3.Connection, root: Path, row: dict) -> dict:
    document_id = int(row["document_id"])
    source_relative = str(row.get("candidate_paths") or "")
    target_relative = str(row.get("db_file_path_before") or "")
    result = {
        "document_id": document_id,
        "instance_id": int(row["instance_id"]),
        "source_path": source_relative,
        "target_path": target_relative,
        "expected_size": int(row.get("candidate_size") or 0),
        "expected_sha256": row.get("candidate_sha256"),
        "source_control_characters": has_control(source_relative),
        "target_control_characters": has_control(target_relative),
        "blockers": [],
        "status": "PENDING",
    }
    if int(row.get("candidate_count") or 0) != 1:
        result["blockers"].append("candidate_count_not_one")
    try:
        source = safe_path(root, source_relative)
        target = safe_path(root, target_relative)
    except ValueError as exc:
        result["blockers"].append(str(exc))
        return result
    if source == target:
        result["blockers"].append("source_equals_target")
    if result["target_control_characters"]:
        result["blockers"].append("target_contains_control_character")
    db_row = db.execute(
        "SELECT file_path, file_name, file_size, instance_id FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    if db_row is None:
        result["blockers"].append("db_row_missing")
        return result
    result["db_file_path_current"] = db_row[0]
    result["db_file_name"] = db_row[1]
    result["db_file_size"] = db_row[2]
    result["db_instance_id"] = db_row[3]
    if db_row[0] != target_relative:
        result["blockers"].append("db_path_changed_since_mapping")
    if int(db_row[3] or -1) != int(row["instance_id"]):
        result["blockers"].append("instance_id_changed_since_mapping")
    if source.exists() and source.is_file():
        size = source.stat().st_size
        result["source_size"] = size
        result["source_sha256"] = sha256(source)
        result["magic_matches_extension"] = magic_matches(source)
        if size != result["expected_size"] or size != int(db_row[2] or -1):
            result["blockers"].append("size_mismatch")
        if result["expected_sha256"] and result["source_sha256"] != result["expected_sha256"]:
            result["blockers"].append("hash_mismatch")
        if not result["magic_matches_extension"]:
            result["blockers"].append("magic_mismatch")
        if target.exists():
            result["blockers"].append("target_collision")
    elif target.exists() and target.is_file():
        result["target_size"] = target.stat().st_size
        result["target_sha256"] = sha256(target)
        if (
            result["target_size"] == result["expected_size"]
            and (not result["expected_sha256"] or result["target_sha256"] == result["expected_sha256"])
        ):
            result["status"] = "ALREADY_APPLIED"
        else:
            result["blockers"].append("source_missing_target_mismatch")
    else:
        result["blockers"].append("source_missing")
    if result["status"] != "ALREADY_APPLIED":
        result["status"] = "READY" if not result["blockers"] else "BLOCKED"
    return result


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="explicitly allow rename/DB transaction")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY_RUN"
    targets = load_targets(args.mapping)
    db = sqlite3.connect(f"file:{args.db.resolve()}?mode={'rw' if args.apply else 'ro'}", uri=True)
    db.row_factory = sqlite3.Row
    results = [inspect(db, args.storage_root.resolve(), row) for row in targets]
    blockers = [row for row in results if row["status"] == "BLOCKED"]
    ready = [row for row in results if row["status"] == "READY"]
    already = [row for row in results if row["status"] == "ALREADY_APPLIED"]
    payload = {
        "task": "021",
        "mode": mode,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": "approach_2_short_term_normalize_physical_name_to_existing_normal_db_path",
        "frozen_target_count": EXPECTED_COUNT,
        "excluded_document_ids": sorted(EXCLUDED_IDS),
        "summary": {
            "target_count": len(results),
            "ready_count": len(ready),
            "blocked_count": len(blockers),
            "already_applied_count": len(already),
            "actual_file_changes": 0,
            "actual_db_path_changes": 0,
        },
        "items": results,
    }
    if not args.apply:
        write_json(args.output, payload)
        print(json.dumps(payload["summary"], ensure_ascii=False))
        return 0 if not blockers else 2

    if blockers or len(ready) + len(already) != EXPECTED_COUNT:
        payload["apply_aborted"] = "precheck_failed"
        write_json(args.output, payload)
        return 2

    renamed: list[tuple[Path, Path]] = []
    db.execute("BEGIN IMMEDIATE")
    try:
        for item in ready:
            source = safe_path(args.storage_root.resolve(), item["source_path"])
            target = safe_path(args.storage_root.resolve(), item["target_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            os.rename(source, target)
            renamed.append((source, target))
            if target.stat().st_size != item["expected_size"] or sha256(target) != item["source_sha256"]:
                raise RuntimeError(f"post-rename verification failed for document {item['document_id']}")
            cursor = db.execute(
                "UPDATE documents SET file_path = file_path WHERE id = ? AND file_path = ?",
                (item["document_id"], item["db_file_path_current"]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"DB compare-and-set failed for document {item['document_id']}")
        db.commit()
    except Exception as exc:
        db.rollback()
        rollback_errors = []
        for source, target in reversed(renamed):
            try:
                if target.exists() and not source.exists():
                    os.rename(target, source)
            except Exception as rollback_exc:  # pragma: no cover - operator emergency path
                rollback_errors.append(str(rollback_exc))
        payload["apply_error"] = str(exc)
        payload["rollback_errors"] = rollback_errors
        write_json(args.output, payload)
        return 3

    payload["summary"]["actual_file_changes"] = len(renamed)
    payload["summary"]["actual_db_path_changes"] = 0
    payload["applied_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(args.output, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
