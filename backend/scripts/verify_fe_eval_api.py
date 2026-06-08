"""기능인제 평가 API 스모크 검증. Usage: cd backend && PYTHONPATH=. python scripts/verify_fe_eval_api.py"""
from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.enums import Role, UIType  # noqa: E402
from app.modules.functional_eval.eval_catalog import catalog_for_api, compute_assessment, get_criteria  # noqa: E402
from app.modules.functional_eval import models as fe_models  # noqa: F401
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalWorker  # noqa: E402
from app.modules.functional_eval import service  # noqa: E402
from app.modules.sites.models import Site  # noqa: E402
from app.modules.users.models import User  # noqa: E402
from app.modules.workers import models as worker_models  # noqa: F401


def main() -> int:
    init_db()
    db = SessionLocal()
    errors: list[str] = []

    try:
        cat = catalog_for_api()
        fc = len(cat["FUNCTIONAL"]["criteria"])
        sc = len(cat["SAFETY"]["criteria"])
        print(f"[OK] eval catalog: functional={fc} safety={sc}")
        if fc < 1 or sc < 1:
            errors.append("catalog empty")

        criteria = get_criteria("FUNCTIONAL")
        scores = {c["id"]: c["grades"][0]["key"] for c in criteria}
        computed = compute_assessment("FUNCTIONAL", scores)
        print(f"[OK] compute_assessment: {computed['total_score']}/{computed['max_score']} {computed['grade_label']}")

        period = service.get_or_create_active_period(db)
        site = db.query(Site).filter(Site.site_code == "__VERIFY_FE__").first()
        if site is None:
            site = Site(site_code="__VERIFY_FE__", site_name="검증현장")
            db.add(site)
            db.flush()
        user = db.query(User).filter(User.login_id == "__VERIFY_FE__").first()
        if user is None:
            user = User(
                name="검증소장",
                login_id="__VERIFY_FE__",
                password_hash="x",
                role=Role.SITE_FUNCTIONAL_EVAL,
                ui_type=UIType.SITE,
                site_id=site.id,
                must_change_password=False,
            )
            db.add(user)
            db.flush()

        rrn = "9901011234567"
        rrn_hash = hashlib.sha256(rrn.encode()).hexdigest()
        worker = (
            db.query(FunctionalEvalWorker)
            .filter(FunctionalEvalWorker.period_id == period.id, FunctionalEvalWorker.rrn_hash == rrn_hash)
            .first()
        )
        if worker is None:
            worker = FunctionalEvalWorker(
                period_id=period.id,
                site_code="__VERIFY_FE__",
                row_no=1,
                name="검증근로자",
                rrn_hash=rrn_hash,
                is_site_manager=False,
                is_active=True,
            )
            db.add(worker)
            db.commit()
            db.refresh(worker)

        saved = service.save_worker_assessment(db, user, worker.id, "FUNCTIONAL", scores)
        assert saved and saved["is_complete"]
        print(f"[OK] save FUNCTIONAL assessment: {saved['grade_label']}")

        got = service.get_worker_assessment(db, user, worker.id, "FUNCTIONAL")
        assert got["assessment"] is not None
        print("[OK] get_worker_assessment")

        items = service.list_workers_for_user(db, user, period)
        w = next((x for x in items if x["id"] == worker.id), None)
        if not w or not w.get("functional_assessment", {}).get("is_complete"):
            errors.append("worker list missing functional_assessment")
        else:
            print("[OK] list_workers includes functional_assessment")

    except Exception as exc:
        errors.append(str(exc))
        print(f"[FAIL] {exc}")
    finally:
        db.close()

    if errors:
        print("\nFAILED:", "; ".join(errors))
        return 1
    print("\nAll evaluation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
