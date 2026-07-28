"""신규현장 배포 현황 — 항목·임계값·권한 상수."""

from __future__ import annotations

# 공사금액(원) — 선임·지정 안내
AMOUNT_SAFETY_HEALTH_MANAGER = 5_000_000_000  # 50억 이상 — 안전보건관리책임자
AMOUNT_SAFETY_MANAGER = 2_000_000_000  # 20억 이상 — 안전관리자

SAFETY_DEPLOYMENT_ITEMS: tuple[tuple[str, str], ...] = (
    ("new_banner", "신규배너"),
    ("core_keywords", "핵심키워드"),
    ("support_33_poster", "33지원제도포스터"),
    ("emergency_card", "비상대응카드"),
    ("functional_eval_poster", "기능인인정제포스터"),
    ("smart_board_4", "스마트게시판4종"),
)

REQUIRED_DOCUMENT_TYPES: tuple[tuple[str, str], ...] = (
    ("initial_risk_assessment", "최초위험성평가"),
    ("safety_health_plan", "안전보건관리계획서"),
    ("emergency_response_plan", "비상대응계획"),
)

# 공사관리팀 — 외주구매와 동일 업무(안전 배포 체크 포함) 담당 (login_id)
CONSTRUCTION_MANAGEMENT_NEW_SITE_EDIT_LOGINS: frozenset[str] = frozenset(
    {
        "공사관리-이재용",
        "공사관리-전용성",
        "공사관리-강태원",
        "공사관리-김종현",
        "공사관리-박성수",
    }
)

# 외주구매 / 공사관리 — 안전 배포 체크 담당 (login_id)
PROCUREMENT_SAFETY_CHECK_LOGINS: frozenset[str] = frozenset(
    {
        "외주구매-신영석",
        "외주구매-주창오",
        "공사관리-이재용",
        "공사관리-전용성",
        "공사관리-강태원",
        "공사관리-김종현",
        "공사관리-박성수",
    }
)

HQ_DEPLOYMENT_ROLES = frozenset(
    {
        "HQ_SAFE",
        "HQ_SAFE_ADMIN",
        "SUPER_ADMIN",
        "HQ_BUDGET_ESTIMATE",
        "HQ_OUTSOURCING_PURCHASE",
    }
)

BUDGET_EDIT_ROLES = frozenset({"HQ_BUDGET_ESTIMATE", "HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"})
PROCUREMENT_EDIT_ROLES = frozenset({"HQ_OUTSOURCING_PURCHASE", "HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"})

ADMIN_ROLES: tuple[tuple[str, str], ...] = (
    ("SITE_MANAGER", "현장소장"),
    ("GONGMU", "공무"),
    ("SAFETY", "안전(관리자)"),
    ("CONSTRUCTION_SUPERVISOR", "공사(관리감독자)"),
    ("OTHER", "기타"),
)

ADMIN_ROLE_KEYS = frozenset(k for k, _ in ADMIN_ROLES)
ADMIN_PROVISION_LOGIN_ROLES = frozenset({"SITE_MANAGER", "GONGMU"})
