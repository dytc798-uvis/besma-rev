"""기능인제 전체 승인 흐름 API 시뮬레이션 + 결과 JSON 저장.

Usage:
  cd backend && PYTHONPATH=. python scripts/run_fe_e2e_simulation.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

REPORT_DIR = BACKEND_ROOT.parent / "docs" / "reports" / "functional-eval-e2e"
REPORT_JSON = REPORT_DIR / "simulation-result.json"

SITE_CODE = "24025"
MANAGER = ("대우청라-박명식", "661123")
LEADER = ("대우청라-김팀장", "750101")
HQ = ("안전보건-조동문", "600321")
CEO = ("부현대표-김홍수", "611001")
BASE = "http://127.0.0.1:8001"


def _top_scores(client: TestClient, eval_type: str) -> dict[str, str]:
    res = client.get("/functional-eval/eval-catalog")
    res.raise_for_status()
    criteria = res.json()[eval_type]["criteria"]
    return {c["id"]: c["grades"][0]["key"] for c in criteria}


def _login(client: TestClient, login_id: str, password: str) -> None:
    res = client.post("/auth/login", data={"username": login_id, "password": password})
    if res.status_code != 200:
        raise RuntimeError(f"login failed {login_id}: {res.status_code} {res.text}")
    token = res.json().get("access_token")
    if not token:
        raise RuntimeError(f"login missing token for {login_id}")
    client.headers["Authorization"] = f"Bearer {token}"


def _logout(client: TestClient) -> None:
    client.headers.pop("Authorization", None)


def _evaluate_all(client: TestClient, worker_ids: list[int]) -> list[str]:
    fn_scores = _top_scores(client, "FUNCTIONAL")
    sf_scores = _top_scores(client, "SAFETY")
    errors: list[str] = []
    for wid in worker_ids:
        for eval_type, scores in [("FUNCTIONAL", fn_scores), ("SAFETY", sf_scores)]:
            r = client.put(f"/functional-eval/workers/{wid}/assessment/{eval_type}", json={"scores": scores})
            if r.status_code != 200:
                errors.append(f"worker={wid} {eval_type}: {r.status_code} {r.text}")
    return errors


def _worker_ids(body: dict) -> list[int]:
    return [w["id"] for w in body.get("items") or []]


def run() -> dict:
    init_db()
    steps: list[dict] = []
    issues: list[dict] = []

    with TestClient(app) as client:
        _login(client, *LEADER)
        leader_res = client.get("/functional-eval/my-site/workers")
        leader_body = leader_res.json()
        steps.append(
            {
                "step": "1_team_leader_workers",
                "actor": LEADER[0],
                "status": leader_res.status_code,
                "role": leader_body.get("evaluator", {}).get("role"),
                "worker_count": len(leader_body.get("items") or []),
                "team_split": leader_body.get("evaluator", {}).get("team_split_active"),
            }
        )
        if leader_res.status_code != 200:
            issues.append({"step": 1, "severity": "error", "message": leader_res.text})
        else:
            errs = _evaluate_all(client, _worker_ids(leader_body))
            steps.append({"step": "1_team_leader_evaluate", "errors": errs})
            if errs:
                issues.append({"step": 1, "severity": "error", "message": "; ".join(errs)})

        _logout(client)
        _login(client, *MANAGER)
        mgr_res = client.get("/functional-eval/my-site/workers")
        mgr_body = mgr_res.json()
        overview = mgr_body.get("site_overview") or []
        steps.append(
            {
                "step": "2_manager_workers",
                "actor": MANAGER[0],
                "status": mgr_res.status_code,
                "direct_count": len(mgr_body.get("items") or []),
                "overview_count": len(overview),
                "approval": mgr_body.get("approval"),
            }
        )
        if mgr_res.status_code != 200:
            issues.append({"step": 2, "severity": "error", "message": mgr_res.text})
        else:
            errs = _evaluate_all(client, _worker_ids(mgr_body))
            steps.append({"step": "2_manager_direct_evaluate", "errors": errs})
            if errs:
                issues.append({"step": 2, "severity": "error", "message": "; ".join(errs)})

            mgr_res2 = client.get("/functional-eval/my-site/workers")
            approval = mgr_res2.json().get("approval") or {}
            steps.append({"step": "2_manager_approval_check", "approval": approval})
            if not approval.get("can_submit_site_approval"):
                issues.append(
                    {
                        "step": 2,
                        "severity": "error",
                        "message": f"현장 승인 불가: incomplete={approval.get('incomplete_count')}",
                    }
                )
            else:
                sub = client.post("/functional-eval/my-site/approval/submit")
                steps.append({"step": "2_manager_submit", "status": sub.status_code, "body": sub.text[:500]})
                if sub.status_code != 200:
                    issues.append({"step": 2, "severity": "error", "message": sub.text})

        _logout(client)
        _login(client, *HQ)
        hq_pending = client.get("/functional-eval/hq/approvals/pending")
        hq_body = hq_pending.json()
        steps.append(
            {
                "step": "3_hq_pending",
                "actor": HQ[0],
                "status": hq_pending.status_code,
                "items": hq_body.get("items") if hq_pending.status_code == 200 else hq_body,
            }
        )
        if hq_pending.status_code != 200:
            issues.append({"step": 3, "severity": "error", "message": hq_pending.text})
        else:
            items = hq_body.get("items") or []
            target = next((x for x in items if x.get("site_code") == SITE_CODE), None)
            if not target:
                issues.append({"step": 3, "severity": "error", "message": f"{SITE_CODE} not in HQ pending"})
            else:
                appr = client.post(f"/functional-eval/hq/approvals/{SITE_CODE}/approve")
                steps.append({"step": "3_hq_approve", "status": appr.status_code, "body": appr.text[:500]})
                if appr.status_code != 200:
                    issues.append({"step": 3, "severity": "error", "message": appr.text})

        _logout(client)
        _login(client, *CEO)
        ceo_pending = client.get("/functional-eval/hq/ceo-approvals/pending")
        ceo_body = ceo_pending.json()
        steps.append(
            {
                "step": "4_ceo_pending",
                "actor": CEO[0],
                "status": ceo_pending.status_code,
                "items": ceo_body.get("items") if ceo_pending.status_code == 200 else ceo_body,
            }
        )
        if ceo_pending.status_code != 200:
            issues.append(
                {
                    "step": 4,
                    "severity": "critical",
                    "message": f"CEO pending list failed: {ceo_pending.text}",
                    "note": "list_ceo_pending was SUPER_ADMIN-only; fixed to assert_ceo_approver",
                }
            )
        else:
            items = ceo_body.get("items") or []
            target = next((x for x in items if x.get("site_code") == SITE_CODE), None)
            if not target:
                issues.append({"step": 4, "severity": "error", "message": f"{SITE_CODE} not in CEO pending"})
            else:
                appr = client.post(f"/functional-eval/hq/ceo-approvals/{SITE_CODE}/approve")
                steps.append({"step": "4_ceo_approve", "status": appr.status_code, "body": appr.text[:500]})
                if appr.status_code != 200:
                    issues.append({"step": 4, "severity": "error", "message": appr.text})

        _logout(client)
        _login(client, *CEO)
        final = client.get("/functional-eval/hq/ceo-approvals/pending")
        steps.append(
            {
                "step": "5_ceo_pending_after",
                "status": final.status_code,
                "count": len(final.json().get("items") or []),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "site_code": SITE_CODE,
        "accounts": {
            "team_leader": {"login_id": LEADER[0], "password": LEADER[1]},
            "manager": {"login_id": MANAGER[0], "password": MANAGER[1]},
            "hq": {"login_id": HQ[0], "password": HQ[1]},
            "ceo": {"login_id": CEO[0], "password": CEO[1]},
        },
        "steps": steps,
        "issues": issues,
        "passed": len(issues) == 0,
    }


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    result = run()
    REPORT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
