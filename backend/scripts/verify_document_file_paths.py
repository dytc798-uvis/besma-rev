"""현장 제출 문서 file_path 무결성 점검 — 배포 전·장애 후 실행용.

사용:
  cd backend && PYTHONPATH=. python scripts/verify_document_file_paths.py
  cd backend && PYTHONPATH=. python scripts/verify_document_file_paths.py --document-type DAILY_TBM
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.modules.documents.storage_paths import resolve_existing_storage_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify documents.file_path resolves on disk")
    parser.add_argument("--document-type", default=None, help="e.g. DAILY_TBM")
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(f"sqlite:///{settings.sqlite_path}")
    Session = sessionmaker(bind=engine)
    db = Session()

    sql = """
        SELECT id, instance_id, document_type, period_start, file_path, file_name, version_no
        FROM documents
        WHERE file_path IS NOT NULL AND TRIM(file_path) != ''
    """
    params: dict = {}
    if args.document_type:
        sql += " AND document_type = :dtype"
        params["dtype"] = args.document_type.strip().upper()
    sql += " ORDER BY period_start DESC, id DESC LIMIT :lim"
    params["lim"] = args.limit

    rows = db.execute(text(sql), params).fetchall()
    missing: list[tuple] = []
    for row in rows:
        resolved = resolve_existing_storage_path(
            settings.storage_root,
            row.file_path,
            instance_id=row.instance_id,
            file_name=row.file_name,
            version_no=row.version_no,
        )
        if resolved is None:
            missing.append(row)

    print(f"checked={len(rows)} missing={len(missing)} storage_root={settings.storage_root}")
    for row in missing[:50]:
        print(
            f"  doc_id={row.id} type={row.document_type} period={row.period_start} "
            f"inst={row.instance_id} path={row.file_path!r}"
        )
    if len(missing) > 50:
        print(f"  ... and {len(missing) - 50} more")

    db.close()
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
