"""Diagnose document upload history file paths vs disk (run on server)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.settings import get_settings
from app.modules.documents.storage_paths import legacy_disk_name_to_target_relative

IDS = [162, 158, 167, 169, 104]
DB = Path("/home/ubuntu/besma-rev/database/besma.db")


def main() -> None:
    settings = get_settings()
    root = settings.storage_root
    print("storage_root:", root)
    conn = sqlite3.connect(DB)
    try:
        for hid in IDS:
            row = conn.execute(
                "SELECT h.id, h.document_id, h.instance_id, h.version_no, h.file_path, h.file_name, "
                "d.file_path AS doc_path "
                "FROM document_upload_histories h "
                "LEFT JOIN documents d ON d.id = h.document_id "
                "WHERE h.id = ?",
                (hid,),
            ).fetchone()
            if not row:
                print(f"id={hid}: NO ROW")
                continue
            _, doc_id, inst_id, ver, rel, fname, doc_path = row
            rel = rel or ""
            direct = root / rel if rel else None
            print(f"\nid={hid} doc={doc_id} inst={inst_id} ver={ver}")
            print(f"  history_path={rel!r} exists={direct.is_file() if direct else False}")
            if rel and inst_id:
                migrated = legacy_disk_name_to_target_relative(
                    instance_id=int(inst_id),
                    disk_name=Path(rel).name,
                    file_name=fname,
                    version_no=int(ver or 1),
                )
                if migrated:
                    mig = root / migrated
                    print(f"  migrated={migrated!r} exists={mig.is_file()}")
            if doc_path:
                dp = root / doc_path
                print(f"  doc_current={doc_path!r} exists={dp.is_file()}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
