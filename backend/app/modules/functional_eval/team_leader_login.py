"""팀장 평가자 login_id 중복 해소."""

from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy.orm import Session

from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSiteRegistry, FunctionalEvalWorker
from app.modules.functional_eval.site_alias import build_eval_login_id

# 이름 → 우선 site_code (별칭 충돌 시 명시 통일)
TEAM_LEADER_SITE_OVERRIDES: dict[str, str] = {
    "임정석": "25002",  # 스타필드 청라 소방전기공사
}


def _normalize_person_name(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", (text or "").strip()).lower()


def normalize_login_to_person_name(login_id: str) -> str:
    login_id = (login_id or "").strip()
    if not login_id:
        return ""
    if "-" in login_id:
        login_id = login_id.split("-", 1)[1]
    return _normalize_person_name(login_id)


def build_eval_login_id_for_site(db: Session, site_code: str, person_name: str) -> str:
    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == (site_code or "").strip())
        .first()
    )
    if reg is None:
        return ""
    return build_eval_login_id((reg.site_alias or "").strip(), person_name)


def _site_worker_count(db: Session, site_code: str, period_id: int) -> int:
    return (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.site_code == site_code,
            FunctionalEvalWorker.period_id == period_id,
        )
        .count()
    )


def _login_to_registry_site_code(db: Session, login_id: str, person_name: str) -> str | None:
    regs = db.query(FunctionalEvalSiteRegistry).all()
    for reg in regs:
        built = build_eval_login_id((reg.site_alias or "").strip(), person_name)
        if built == login_id:
            return (reg.site_code or "").strip()
    return None


def resolve_canonical_team_leader_login(
    db: Session,
    *,
    site_code: str,
    person_name: str,
    candidate_logins: set[str] | list[str],
    period_id: int | None = None,
) -> str:
    """동일 팀장 이름의 후보 login_id 중 canonical 1개 선택."""
    person_name = (person_name or "").strip()
    candidates = sorted({(x or "").strip() for x in candidate_logins if (x or "").strip()})
    if not person_name:
        return candidates[0] if candidates else ""

    override_code = TEAM_LEADER_SITE_OVERRIDES.get(person_name)
    if override_code:
        preferred = build_eval_login_id_for_site(db, override_code, person_name)
        if preferred:
            return preferred

    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == (site_code or "").strip())
        .first()
    )
    if reg is not None:
        preferred = build_eval_login_id((reg.site_alias or "").strip(), person_name)
        if preferred:
            if not candidates or preferred in candidates:
                return preferred

    if len(candidates) == 1:
        return candidates[0]

    if period_id is not None:
        login_site: dict[str, str] = {}
        for login in candidates:
            mapped = _login_to_registry_site_code(db, login, person_name)
            if mapped:
                login_site[login] = mapped
        if login_site:
            return min(
                login_site.keys(),
                key=lambda login: _site_worker_count(db, login_site[login], period_id),
            )

    return candidates[0]


def collect_team_leader_evaluator_logins_deduped(
    db: Session,
    rows: list[FunctionalEvalWorker],
    manager_login: str,
    *,
    site_code: str,
    period_id: int,
) -> set[str]:
    """팀원 배정 login_id를 팀장 이름 기준 dedupe."""
    manager_login = (manager_login or "").strip()
    by_name: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        assigned = (row.assigned_evaluator_login_id or "").strip()
        if not assigned or assigned == manager_login:
            continue
        name_key = normalize_login_to_person_name(assigned)
        if not name_key:
            continue
        by_name[name_key].add(assigned)

    out: set[str] = set()
    for name_key, logins in by_name.items():
        display_name = next(iter(logins)).split("-", 1)[-1] if logins else ""
        canonical = resolve_canonical_team_leader_login(
            db,
            site_code=site_code,
            person_name=display_name,
            candidate_logins=logins,
            period_id=period_id,
        )
        if canonical:
            out.add(canonical)
    return out


def reconcile_team_leader_assignments(
    db: Session,
    period: FunctionalEvalPeriod,
    site_code: str,
) -> int:
    """현장 내 팀장 login_id를 canonical로 통일. 변경 건수 반환."""
    site_code = (site_code or "").strip()
    if not site_code:
        return 0

    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == site_code)
        .first()
    )
    manager_login = ((reg.manager_login_id if reg else None) or "").strip()

    workers = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.period_id == period.id,
            FunctionalEvalWorker.site_code == site_code,
        )
        .all()
    )

    by_name: dict[str, set[str]] = defaultdict(set)
    for worker in workers:
        assigned = (worker.assigned_evaluator_login_id or "").strip()
        if not assigned or assigned == manager_login:
            continue
        name_key = normalize_login_to_person_name(assigned)
        if name_key:
            by_name[name_key].add(assigned)

    canonical_by_name: dict[str, str] = {}
    for name_key, logins in by_name.items():
        display_name = next(iter(logins)).split("-", 1)[-1]
        canonical_by_name[name_key] = resolve_canonical_team_leader_login(
            db,
            site_code=site_code,
            person_name=display_name,
            candidate_logins=logins,
            period_id=period.id,
        )

    changed = 0
    for worker in workers:
        assigned = (worker.assigned_evaluator_login_id or "").strip()
        if not assigned or assigned == manager_login:
            continue
        name_key = normalize_login_to_person_name(assigned)
        canonical = canonical_by_name.get(name_key)
        if canonical and assigned != canonical:
            worker.assigned_evaluator_login_id = canonical
            db.add(worker)
            changed += 1
    return changed
