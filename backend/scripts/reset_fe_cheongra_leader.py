"""대우청라 김팀장 평가완료(서명) 삭제 + 타 평가자 평가보고서 null (로컬 데모용).

- 김팀장: TEAM_LEADER·TEAM_MANAGER_APPROVE 서명·PDF 삭제 (팀원 평가 데이터는 유지)
- 그 외: functional_eval_signatures 전부 삭제 (평가보고서 null 상태)
- 동의서(FunctionalEvalConsent)는 유지

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
    FunctionalEvalSignature,
)
from app.modules.sites.models import Site  # noqa: F401
from app.modules.users.models import User  # noqa: F401

LEADER_LOGIN = "대우청라-김팀장"


def _delete_signature_pdfs() -> int:
    sig_dir = settings.storage_root / "functional_eval" / "signatures"
    deleted = 0
    if sig_dir.is_dir():
        for pdf in sig_dir.glob("*.pdf"):
            pdf.unlink(missing_ok=True)
            deleted += 1
    return deleted


def reset_eval_signatures(db) -> tuple[int, int]:
    """김팀장 평가완료 + 전체 평가보고서 서명 초기화."""
    leader_rows = (
        db.query(FunctionalEvalSignature)
        .filter(FunctionalEvalSignature.team_leader_login_id == LEADER_LOGIN)
        .all()
    )
    leader_deleted = len(leader_rows)
    for row in leader_rows:
        db.delete(row)

    other_deleted = (
        db.query(FunctionalEvalSignature)
        .filter(
            (FunctionalEvalSignature.team_leader_login_id.is_(None))
            | (FunctionalEvalSignature.team_leader_login_id != LEADER_LOGIN)
        )
        .delete(synchronize_session=False)
    )
    return leader_deleted, other_deleted


def main() -> None:
    deleted_files = _delete_signature_pdfs()

    db = SessionLocal()
    try:
        leader_deleted, other_deleted = reset_eval_signatures(db)
        db.commit()
        print(f"PDF 삭제: {deleted_files}개")
        print(f"김팀장 평가완료(서명) 삭제: {leader_deleted}건")
        print(f"기타 평가자 평가보고서(null): {other_deleted}건")
        print(f"팀원 평가 데이터는 유지 - {LEADER_LOGIN} / 750101")
    finally:
        db.close()


if __name__ == "__main__":
    main()
