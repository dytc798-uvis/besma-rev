"""신규현장 로그인 별칭 — 예: [2.신세계건설] 스타필드 창원… → 신세계스타창원."""

from __future__ import annotations

import re

from app.modules.functional_eval.site_alias import build_eval_login_id, derive_site_alias


def derive_deployment_site_alias(contractor: str | None, site_name: str) -> str:
    contractor_text = (contractor or "").strip()
    name_text = (site_name or "").strip()
    combined = f"[{contractor_text}] {name_text}" if contractor_text else name_text

    if "스타필드" in name_text and "창원" in name_text:
        prefix = "신세계" if "신세계" in contractor_text or "신세계" in name_text else ""
        if not prefix:
            m = re.search(r"([가-힣]{2,4})건설", contractor_text)
            prefix = m.group(1) if m else derive_site_alias(combined)[:4]
        return f"{prefix}스타창원"[:20]

    return derive_site_alias(combined)


def build_manager_login_ids(
    site_alias: str,
    *,
    site_manager_name: str | None,
    gongmu_name: str | None,
) -> tuple[str | None, str | None]:
    mgr = build_eval_login_id(site_alias, site_manager_name or "")
    gongmu = build_eval_login_id(site_alias, gongmu_name or "")
    return (mgr or None, gongmu or None)
