from __future__ import annotations

import hashlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import settings
from app.core.database import SessionLocal
from app.modules.risk_library.models import (
    RiskLibraryItem,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
)
from app.modules.risk_library.service import recommend_risks_for_work_item


SEARCH_TERMS = [
    "배관",
    "천장슬라브 배관",
    "벽체 배관",
    "전선관 배관",
    "배선",
    "전기 설비 설치",
    "전주",
    "감전",
    "추락",
]


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _print_counts(db) -> None:
    items = db.query(RiskLibraryItem).count()
    revisions = db.query(RiskLibraryItemRevision).count()
    keywords = db.query(RiskLibraryKeyword).count()
    print(f"risk_library_items: {items}")
    print(f"risk_library_item_revisions: {revisions}")
    print(f"risk_library_keywords: {keywords}")


def _search(db, term: str, limit: int = 5) -> list[dict]:
    return recommend_risks_for_work_item(
        db,
        work_name=term,
        work_description=term,
        top_n=limit,
    )


def main() -> None:
    db_path = Path(settings.sqlite_path).resolve()
    print(f"sqlite_path={db_path}")
    print(f"db_exists={db_path.exists()}")
    if not db_path.exists():
        return

    stat = db_path.stat()
    print(f"db_size_bytes={stat.st_size}")
    print(f"db_mtime={stat.st_mtime}")
    print(f"db_sha256={_file_sha256(db_path)}")

    db = SessionLocal()
    try:
        _print_counts(db)
        for term in SEARCH_TERMS:
            rows = _search(db, term)
            print(f"\n[search] {term} -> {len(rows)} hit(s)")
            for idx, row in enumerate(rows, start=1):
                rev_id = row.get("risk_revision_id")
                score = float(row.get("score", 0.0))
                process = row.get("process") or row.get("work_category") or ""
                risk_factor = row.get("risk_factor") or ""
                countermeasure = row.get("countermeasure") or ""
                print(
                    f"  {idx}. rev={rev_id} score={score:.1f} "
                    f"process={process} risk_factor={risk_factor} "
                    f"counterplan={countermeasure}"
                )
    finally:
        db.close()


if __name__ == "__main__":
    main()
