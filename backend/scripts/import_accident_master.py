from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.accidents import service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Import BESMA MASTER accidents into DB")
    parser.add_argument(
        "--xlsx",
        default=r"Z:\4. 안전보건관리실\104 사고 조사 및 이력 (산재요양승인 내역)\BESMA_사고MASTER_2026.xlsx",
        help="MASTER xlsx path",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        result = service.import_master_rows(db, workbook_path=Path(args.xlsx))
        print(f"[accident-master-import] imported={result['imported']} skipped={result['skipped']}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
