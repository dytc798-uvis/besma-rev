from __future__ import annotations

from pathlib import Path

from app.modules.safety_features import routes as safety_routes


def test_nonconformity_list_route_before_param_route():
    """정적 GET /nonconformities/items 가 /nonconformities/{ledger_id} 보다 먼저 등록되어야 한다."""
    get_paths: list[tuple[str, int]] = []
    for i, r in enumerate(safety_routes.router.routes):
        p = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        if p and "GET" in methods:
            get_paths.append((p, i))
    idx_items = next(i for p, i in get_paths if str(p).endswith("/nonconformities/items"))
    idx_overview = next(i for p, i in get_paths if str(p).endswith("/nonconformities/overview/current"))
    idx_param = next(i for p, i in get_paths if str(p).endswith("/nonconformities/{ledger_id}"))
    assert idx_items < idx_param
    assert idx_overview < idx_param


def test_site_documents_dashboard_hides_ledger_managed_uploads():
    """내 현장 문서: 전용 대장 문서 코드 가드 유지."""
    root = Path(__file__).resolve().parents[2]
    vue = (root / "frontend" / "src" / "pages" / "site" / "SiteDocumentsDashboardPage.vue").read_text(encoding="utf-8")
    assert "AUTO_WORKER_OPINION_LOG" in vue
    assert "NONCONFORMITY_ACTION_REPORT" in vue
    assert "isLedgerManagedRequirement" in vue
    assert "openUpload" in vue

