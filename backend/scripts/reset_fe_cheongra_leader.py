"""대우청라 김팀장 — 깨진 PDF·서명·평가 초기화 (로컬 데모용).

Usage:
  cd backend && PYTHONPATH=. python scripts/reset_fe_cheongra_leader.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.modules.functional_eval import models as fe_models  # noqa: F401
from app.modules.functional_eval.models import (  # noqa: E402
    FunctionalEvalAssessment,
    FunctionalEvalAssessmentRevision,
    FunctionalEvalConsent,
    FunctionalEvalSignature,
    FunctionalEvalWorker,
)
from app.modules.sites.models import Site  # noqa: F401
from app.modules.users.models import User  # noqa: F401

CHEONGRA_CODE = "24025"
LEADER_LOGIN = "대우청라-김팀장"


def main() -> None:
    sig_dir = settings.storage_root / "functional_eval" / "signatures"
    deleted_files = 0
    if sig_dir.is_dir():
        for pdf in sig_dir.glob("*.pdf"):
            pdf.unlink(missing_ok=True)
            deleted_files += 1

    db = SessionLocal()
    try:
        consent_rows = db.query(FunctionalEvalConsent).all()
        consent_deleted = len(consent_rows)
        for row in consent_rows:
            db.delete(row)

        sig_rows = db.query(FunctionalEvalSignature).all()
        sig_deleted = len(sig_rows)
        for row in sig_rows:
            db.delete(row)

        leader_workers = (
            db.query(FunctionalEvalWorker)
            .filter(
                FunctionalEvalWorker.site_code == CHEONGRA_CODE,
                FunctionalEvalWorker.assigned_evaluator_login_id == LEADER_LOGIN,
            )
            .all()
        )
        worker_ids = [w.id for w in leader_workers]

        rev_deleted = 0
        assess_deleted = 0
        if worker_ids:
            rev_deleted = (
                db.query(FunctionalEvalAssessmentRevision)
                .filter(FunctionalEvalAssessmentRevision.worker_id.in_(worker_ids))
                .delete(synchronize_session=False)
            )
            assess_deleted = (
                db.query(FunctionalEvalAssessment)
                .filter(FunctionalEvalAssessment.worker_id.in_(worker_ids))
                .delete(synchronize_session=False)
            )

        db.commit()
        print(f"PDF 삭제: {deleted_files}개 ({sig_dir})")
        print(f"동의서 DB 삭제: {consent_deleted}건")
        print(f"서명 DB 삭제: {sig_deleted}건")
        print(f"김팀장 팀원 평가 삭제: {assess_deleted}건 (수정이력 {rev_deleted}건)")
        print(f"김팀장 담당 근로자 {len(worker_ids)}명 - 다시 평가 가능")
        print(f"로그인: {LEADER_LOGIN} / 750101")
    finally:
        db.close()


if __name__ == "__main__":
    main()
