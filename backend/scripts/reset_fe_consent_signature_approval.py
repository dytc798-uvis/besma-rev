"""기능인제 동의·서명·승인만 초기화 (평가 점수·출역·근로자 유지).

- functional_eval_consents — 전체 삭제
- functional_eval_signatures — 전체 삭제
- functional_eval_site_approvals — 전체 삭제 (다음 조회 시 재생성)
- storage/functional_eval/signatures/*.pdf — 삭제

Usage:
  cd backend && PYTHONPATH=. python scripts/reset_fe_consent_signature_approval.py
  cd backend && PYTHONPATH=. python scripts/reset_fe_consent_signature_approval.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.settings import settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.functional_eval import models as fe_models  # noqa: F401
from app.modules.functional_eval.models import (  # noqa: E402
    FunctionalEvalConsent,
    FunctionalEvalSignature,
    FunctionalEvalSiteApproval,
)


def purge_signature_pdfs(*, dry_run: bool) -> int:
    sig_dir = settings.storage_root / "functional_eval" / "signatures"
    if not sig_dir.is_dir():
        return 0
    count = 0
    for pdf in sig_dir.glob("*.pdf"):
        print(f"pdf: {'would delete' if dry_run else 'delete'} {pdf.name}")
        if not dry_run:
            pdf.unlink(missing_ok=True)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_db()
    pdf_count = purge_signature_pdfs(dry_run=args.dry_run)

    db = SessionLocal()
    try:
        consent_n = db.query(FunctionalEvalConsent).count()
        sig_n = db.query(FunctionalEvalSignature).count()
        appr_n = db.query(FunctionalEvalSiteApproval).count()

        print(f"consents={consent_n} signatures={sig_n} site_approvals={appr_n} pdfs={pdf_count}")

        if args.dry_run:
            print("DRY-RUN - no database changes")
            return

        db.query(FunctionalEvalConsent).delete(synchronize_session=False)
        db.query(FunctionalEvalSignature).delete(synchronize_session=False)
        db.query(FunctionalEvalSiteApproval).delete(synchronize_session=False)
        db.commit()
        print(
            f"DONE deleted consents={consent_n} signatures={sig_n} "
            f"site_approvals={appr_n} pdfs={pdf_count}"
        )
        print("평가 점수·출역·근로자 데이터는 유지됩니다.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
