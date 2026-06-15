#!/usr/bin/env python3
"""기능인제 시행 전 초기화 — 동의·평가·승인 데이터 삭제, 마감일·통계 기준일 설정.

유지: 출역·근로자·현장등록·사용자 계정
삭제: 동의서, 서명, 승인, 평가점수, 제재, 포상, 일일보고 PDF 메타

Usage:
  cd backend
  .venv/bin/python scripts/reset_fe_launch_clean.py --dry-run
  .venv/bin/python scripts/reset_fe_launch_clean.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.settings import settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.functional_eval import models as fe_models  # noqa: F401, E402
from app.modules.functional_eval.constants import DEFAULT_GRADE_STATS_LIVE_FROM  # noqa: E402
from app.modules.functional_eval.eval_schedule import EVAL_CAMPAIGN_DEADLINE  # noqa: E402
from app.modules.functional_eval.models import (  # noqa: E402
    FunctionalEvalAssessment,
    FunctionalEvalAssessmentRevision,
    FunctionalEvalConsent,
    FunctionalEvalCustomerReward,
    FunctionalEvalDailyReport,
    FunctionalEvalPeriod,
    FunctionalEvalSanction,
    FunctionalEvalSignature,
    FunctionalEvalSiteApproval,
    FunctionalEvalWorker,
)


def purge_pdfs(*, dry_run: bool) -> int:
    count = 0
    for sub in ("signatures", "daily_reports", "rewards", "sanctions"):
        d = settings.storage_root / "functional_eval" / sub
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if f.is_file():
                print(f"pdf/file: {'would delete' if dry_run else 'delete'} {f}")
                if not dry_run:
                    f.unlink(missing_ok=True)
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        parser.error("--dry-run 또는 --apply 중 하나를 지정하세요.")

    init_db()
    pdf_n = purge_pdfs(dry_run=args.dry_run)

    db = SessionLocal()
    try:
        counts = {
            "revisions": db.query(FunctionalEvalAssessmentRevision).count(),
            "assessments": db.query(FunctionalEvalAssessment).count(),
            "sanctions": db.query(FunctionalEvalSanction).count(),
            "rewards": db.query(FunctionalEvalCustomerReward).count(),
            "signatures": db.query(FunctionalEvalSignature).count(),
            "consents": db.query(FunctionalEvalConsent).count(),
            "approvals": db.query(FunctionalEvalSiteApproval).count(),
            "daily_reports": db.query(FunctionalEvalDailyReport).count(),
        }
        period = (
            db.query(FunctionalEvalPeriod)
            .filter(FunctionalEvalPeriod.is_active.is_(True))
            .order_by(FunctionalEvalPeriod.id.desc())
            .first()
        )
        print("counts", counts, "pdfs", pdf_n)
        if period:
            print(
                f"period id={period.id} deadline={period.deadline_date} "
                f"grade_stats_live_from={period.grade_stats_live_from}"
            )

        if args.dry_run:
            print("DRY-RUN")
            return

        db.query(FunctionalEvalAssessmentRevision).delete(synchronize_session=False)
        db.query(FunctionalEvalAssessment).delete(synchronize_session=False)
        db.query(FunctionalEvalSanction).delete(synchronize_session=False)
        db.query(FunctionalEvalCustomerReward).delete(synchronize_session=False)
        db.query(FunctionalEvalSignature).delete(synchronize_session=False)
        db.query(FunctionalEvalConsent).delete(synchronize_session=False)
        db.query(FunctionalEvalSiteApproval).delete(synchronize_session=False)
        db.query(FunctionalEvalDailyReport).delete(synchronize_session=False)

        db.query(FunctionalEvalWorker).update(
            {FunctionalEvalWorker.mileage_points: 0, FunctionalEvalWorker.mileage_note: None},
            synchronize_session=False,
        )

        if period:
            period.deadline_date = EVAL_CAMPAIGN_DEADLINE
            period.grade_stats_live_from = DEFAULT_GRADE_STATS_LIVE_FROM
            period.hq_grade_stats_json = None
            period.hq_grade_stats_computed_at = None
            db.add(period)

        db.commit()
        print(
            f"DONE deleted={counts} pdfs={pdf_n} "
            f"deadline={EVAL_CAMPAIGN_DEADLINE} live_from={DEFAULT_GRADE_STATS_LIVE_FROM}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
