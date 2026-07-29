#!/usr/bin/env python3
"""Rollback companion for TASK 021 A-grade recovery.

Default execution is a read-only validation.  `--apply` is required to reverse
renames recorded by a successful apply log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--apply-log", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    log = json.loads(args.apply_log.read_text(encoding="utf-8-sig"))
    rows = [row for row in log.get("items", []) if row.get("status") == "READY"]
    checks = []
    for row in rows:
        source = safe(args.storage_root, row["source_path"])
        target = safe(args.storage_root, row["target_path"])
        ok = (
            target.is_file()
            and not source.exists()
            and target.stat().st_size == int(row["expected_size"])
            and sha256(target) == row["source_sha256"]
        )
        checks.append({"document_id": row["document_id"], "ready": ok})
    result = {
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "target_count": len(rows),
        "ready_count": sum(1 for row in checks if row["ready"]),
        "actual_file_changes": 0,
        "items": checks,
    }
    if args.apply:
        if not all(row["ready"] for row in checks):
            result["aborted"] = "precheck_failed"
        else:
            changed = []
            try:
                by_id = {int(row["document_id"]): row for row in rows}
                for check in reversed(checks):
                    row = by_id[int(check["document_id"])]
                    source = safe(args.storage_root, row["source_path"])
                    target = safe(args.storage_root, row["target_path"])
                    source.parent.mkdir(parents=True, exist_ok=True)
                    os.rename(target, source)
                    changed.append((source, target))
                result["actual_file_changes"] = len(changed)
            except Exception as exc:
                result["error"] = str(exc)
                for source, target in reversed(changed):
                    if source.exists() and not target.exists():
                        os.rename(source, target)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("mode", "target_count", "ready_count", "actual_file_changes")}))
    return 0 if "aborted" not in result and "error" not in result else 2


if __name__ == "__main__":
    sys.exit(main())
