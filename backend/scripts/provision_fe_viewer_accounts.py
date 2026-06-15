#!/usr/bin/env python3
"""본사 조회전용 계정 일괄 생성 CLI.

  cd backend
  .venv/bin/python scripts/provision_fe_viewer_accounts.py --dry-run
  .venv/bin/python scripts/provision_fe_viewer_accounts.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.modules.functional_eval import fe_viewer_provisioning_service as svc


def main() -> int:
    parser = argparse.ArgumentParser(description="본사 조회전용(FUNCTIONAL_EVAL_VIEWER) 계정 일괄 생성")
    parser.add_argument("--dry-run", action="store_true", help="생성 예정·제외 목록만 출력")
    parser.add_argument("--apply", action="store_true", help="실제 users 테이블에 생성")
    parser.add_argument("--source", type=str, default="", help="사원리스트 xls/xlsx 경로(선택)")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        parser.error("--dry-run 또는 --apply 중 하나를 지정하세요.")

    source = Path(args.source) if args.source.strip() else None
    db = SessionLocal()
    try:
        if args.dry_run:
            result = svc.dry_run_viewer_accounts(db, source_path=source)
        else:
            result = svc.apply_viewer_accounts(db, source_path=source, actor=None)
        payload = result.to_dict()
        print(f"mode={payload['mode']} source={payload['source_label']}")
        print(f"planned={payload['planned_count']} excluded={payload['excluded_count']} created={payload.get('created_count', 0)}")
        for row in payload.get("planned", [])[:20]:
            print(f"  + {row.get('login_id')} {row.get('name')}")
        for row in payload.get("excluded", [])[:20]:
            print(f"  - {row.get('name')}: {row.get('reason')}")
        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
