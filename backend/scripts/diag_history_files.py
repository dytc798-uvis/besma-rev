"""Diagnose document upload history file paths vs disk (run on server)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.settings import get_settings
from app.modules.documents.storage_paths import resolve_existing_storage_path

DB = Path("/home/ubuntu/besma-rev/database/besma.db")


def main() -> None:
    settings = get_settings()
    root = settings.storage_root
    print("storage_root:", root)
    conn = sqlite3.connect(DB)
    try:
        rows = conn.execute(
            """
            SELECT h.id, h.document_id, h.instance_id, h.version_no, h.file_path, h.file_name,
                   d.file_path AS doc_path, d.instance_id AS doc_instance_id
            FROM document_upload_histories h
            LEFT JOIN documents d ON d.id = h.document_id
            WHERE h.file_path IS NOT NULL AND TRIM(h.file_path) != ''
            ORDER BY h.id DESC
            LIMIT 200
            """
        ).fetchall()
        missing = 0
        for row in rows:
            hid, doc_id, inst_id, ver, rel, fname, doc_path, doc_inst = row
            inst = inst_id or doc_inst
            resolved = resolve_existing_storage_path(
                root,
                rel or "",
                instance_id=int(inst) if inst else None,
                file_name=fname,
                version_no=int(ver or 1),
            )
            ok = resolved is not None
            if not ok:
                missing += 1
            print(
                f"id={hid} doc={doc_id} inst={inst} ver={ver} ok={ok} "
                f"path={rel!r} resolved={resolved}"
            )
        print(f"\nMISSING: {missing} / {len(rows)} (latest 200 history rows with file_path)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
