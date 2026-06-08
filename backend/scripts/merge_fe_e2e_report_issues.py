"""시뮬레이션 JSON에 수동 검증 이슈·권고를 병합."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = BACKEND_ROOT.parent / "docs" / "reports" / "functional-eval-e2e"
JSON_PATH = REPORT_DIR / "simulation-result.json"

KNOWN_ISSUES = [
    {
        "step": "fix",
        "severity": "critical",
        "message": "대표이사 목록 API(GET /hq/ceo-approvals/pending)가 SUPER_ADMIN만 허용 → 부현대표-김홍수 UI에서 403",
        "note": "routes.py에서 assert_ceo_approver로 수정 완료",
        "status": "fixed",
    },
    {
        "step": "ops",
        "severity": "warn",
        "message": "로컬 DB가 alembic head(0061)인데 0057~0059 컬럼(last_attendance_date, assigned_evaluator_login_id, rep_name) 누락",
        "note": "repair_fe_db_schema.py로 보정. 배포 전 alembic upgrade head 재실행 권장",
        "status": "mitigated",
    },
    {
        "step": "ui",
        "severity": "info",
        "message": "HQ 승인 패널 문구에 'SUPER_ADMIN' 표기 — 실제 CEO 계정은 부현대표-김홍수",
        "note": "HQFunctionalEvalPage.vue 문구 수정 완료",
        "status": "fixed",
    },
    {
        "step": "ui",
        "severity": "info",
        "message": "안전·제재 통합 UI는 로컬만 반영, 운영 미배포",
        "note": "일괄 배포 시 Vercel 포함",
        "status": "open",
    },
]


def main() -> None:
    if not JSON_PATH.exists():
        print("missing simulation-result.json", file=sys.stderr)
        sys.exit(1)
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    open_issues = [i for i in KNOWN_ISSUES if i.get("status") != "fixed"]
    data["known_issues"] = KNOWN_ISSUES
    data["simulation_passed"] = data.get("passed", True)
    data["issues"] = open_issues
    data["passed"] = data["simulation_passed"] and not open_issues
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("merged known issues")


if __name__ == "__main__":
    main()
