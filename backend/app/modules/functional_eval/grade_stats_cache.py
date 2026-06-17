"""본사 등급 통계 스냅샷 — ERP 월별집계 인원 + 출역 근로자 평가 결과를 미리 계산·저장."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.datetime_utils import format_kst_datetime_short, kst_today, utc_now
from app.modules.functional_eval.constants import (
    DEFAULT_GRADE_STATS_LIVE_FROM,
    DEMO_GRADE_RATIOS,
)
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSiteRegistry

GRADE_STAT_CODES: tuple[str, ...] = ("S", "A", "B", "C")
HQ_GRADE_STATS_CACHE_TTL = timedelta(hours=1)


def _live_from_date(period: FunctionalEvalPeriod) -> date:
    return period.grade_stats_live_from or DEFAULT_GRADE_STATS_LIVE_FROM


def is_demo_grade_stats(period: FunctionalEvalPeriod, *, today: date | None = None) -> bool:
    """6/16(KST) 실평가 시작 전이면 가상 등급 분포를 사용."""
    ref = today if today is not None else kst_today()
    return ref < _live_from_date(period)


def _expected_grade_stats_mode(period: FunctionalEvalPeriod) -> str:
    return "demo" if is_demo_grade_stats(period) else "live"


def _allocate_grade_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
    if total <= 0:
        return {code: 0 for code in GRADE_STAT_CODES}
    raw = {code: total * ratios[code] / 100.0 for code in GRADE_STAT_CODES}
    counts = {code: int(raw[code]) for code in GRADE_STAT_CODES}
    remainder = total - sum(counts.values())
    if remainder > 0:
        order = sorted(GRADE_STAT_CODES, key=lambda c: raw[c] - counts[c], reverse=True)
        for idx in range(remainder):
            counts[order[idx % len(order)]] += 1
    return counts


def _synthetic_grade_distribution(
    workers_total: int,
    *,
    attendance_workers: int,
) -> dict[str, Any]:
    graded_total = max(workers_total, 0)
    counts = _allocate_grade_counts(graded_total, DEMO_GRADE_RATIOS)
    grades: dict[str, dict[str, float | int]] = {}
    for code in GRADE_STAT_CODES:
        count = counts[code]
        grades[code] = {
            "count": count,
            "pct": round(100.0 * count / graded_total, 1) if graded_total else 0.0,
        }
    return {
        "workers_total": graded_total,
        "attendance_workers": attendance_workers,
        "graded_total": graded_total,
        "ungraded_count": 0,
        "grades": grades,
        "is_demo": True,
    }


def _synthetic_grade_stats_block(
    workers: list[dict[str, Any]],
    *,
    workers_total: int,
) -> dict[str, Any]:
    attendance_workers = len(workers)
    functional = _synthetic_grade_distribution(
        workers_total,
        attendance_workers=attendance_workers,
    )
    safety = _synthetic_grade_distribution(
        workers_total,
        attendance_workers=attendance_workers,
    )
    return {"functional": functional, "safety": safety}


def _apply_demo_grade_overlay(payload: dict[str, Any], period: FunctionalEvalPeriod) -> dict[str, Any]:
    live_from = _live_from_date(period)
    overall_erp = int(payload.get("erp_headcount_total") or 0)
    overall_att = int((payload.get("overall") or {}).get("functional", {}).get("attendance_workers") or 0)
    overall_total = overall_att if overall_att > 0 else overall_erp

    payload["overall"] = _synthetic_grade_stats_block([], workers_total=overall_total)
    payload["overall"]["functional"]["attendance_workers"] = overall_att
    payload["overall"]["functional"]["erp_headcount"] = overall_erp
    payload["overall"]["safety"]["attendance_workers"] = overall_att
    payload["overall"]["safety"]["erp_headcount"] = overall_erp

    for row in payload.get("by_site") or []:
        erp_total = int(row.get("erp_headcount") or 0)
        att = int((row.get("functional") or {}).get("attendance_workers") or 0)
        workers_total = att if att > 0 else erp_total
        block = _synthetic_grade_stats_block([], workers_total=workers_total)
        block["functional"]["attendance_workers"] = att
        block["functional"]["erp_headcount"] = erp_total
        block["safety"]["attendance_workers"] = att
        block["safety"]["erp_headcount"] = erp_total
        row["functional"] = block["functional"]
        row["safety"] = block["safety"]

    for row in payload.get("by_team") or []:
        erp_total = int(row.get("erp_headcount") or 0)
        att = int((row.get("functional") or {}).get("attendance_workers") or 0)
        workers_total = att if att > 0 else erp_total
        block = _synthetic_grade_stats_block([], workers_total=workers_total)
        block["functional"]["attendance_workers"] = att
        block["functional"]["erp_headcount"] = erp_total
        block["safety"]["attendance_workers"] = att
        block["safety"]["erp_headcount"] = erp_total
        row["functional"] = block["functional"]
        row["safety"] = block["safety"]

    payload["grade_stats_mode"] = "demo"
    payload["grade_stats_mode_label"] = (
        f"가상 등급 분포 ({live_from.month}/{live_from.day} 실평가 시작 전)"
    )
    payload["grade_stats_live_from"] = live_from.isoformat()
    payload["demo_grade_ratios"] = dict(DEMO_GRADE_RATIOS)
    return payload


def _finalize_grade_stats_payload(payload: dict[str, Any], period: FunctionalEvalPeriod) -> dict[str, Any]:
    if is_demo_grade_stats(period):
        return _apply_demo_grade_overlay(payload, period)
    live_from = _live_from_date(period)
    payload["grade_stats_mode"] = "live"
    payload["grade_stats_mode_label"] = None
    payload["grade_stats_live_from"] = live_from.isoformat()
    payload["demo_grade_ratios"] = None
    return payload


def _registry_rows(db: Session) -> list[FunctionalEvalSiteRegistry]:
    return (
        db.query(FunctionalEvalSiteRegistry)
        .order_by(FunctionalEvalSiteRegistry.site_code.asc())
        .all()
    )


def _registry_headcount_map(db: Session) -> dict[str, int]:
    return {
        reg.site_code: int(reg.erp_headcount or 0)
        for reg in _registry_rows(db)
        if reg.site_code
    }


def erp_headcount_total(db: Session) -> int:
    return sum(_registry_headcount_map(db).values())


def _resolve_workers_total(*, erp_total: int, attendance_count: int) -> int:
    """평가·통계 모집단 = 기간 내 실제 출역 인원 (ERP 인원은 참고용)."""
    if attendance_count > 0:
        return attendance_count
    if erp_total > 0:
        return erp_total
    return 0


def _grade_distribution(
    workers: list[dict[str, Any]],
    *,
    assessment_field: str,
    workers_total: int | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval.service import normalize_grade_code

    counts = {code: 0 for code in GRADE_STAT_CODES}
    graded_total = 0
    for worker in workers:
        assessment = worker.get(assessment_field)
        if not assessment or not assessment.get("is_complete"):
            continue
        code = normalize_grade_code(str(assessment.get("grade_code") or "")) or ""
        if code in counts:
            counts[code] += 1
            graded_total += 1

    attendance_workers = len(workers)
    total = _resolve_workers_total(erp_total=int(workers_total or 0), attendance_count=attendance_workers)
    ungraded = max(0, total - graded_total)

    grades: dict[str, dict[str, float | int]] = {}
    for code in GRADE_STAT_CODES:
        count = counts[code]
        grades[code] = {
            "count": count,
            "pct": round(100.0 * count / graded_total, 1) if graded_total else 0.0,
        }
    erp = int(workers_total or 0)
    return {
        "workers_total": total,
        "attendance_workers": attendance_workers,
        "erp_headcount": erp if erp != total else None,
        "graded_total": graded_total,
        "ungraded_count": ungraded,
        "grades": grades,
    }


def _grade_stats_block(
    workers: list[dict[str, Any]],
    *,
    workers_total: int | None = None,
) -> dict[str, Any]:
    return {
        "functional": _grade_distribution(
            workers,
            assessment_field="functional_assessment",
            workers_total=workers_total,
        ),
        "safety": _grade_distribution(
            workers,
            assessment_field="safety_assessment",
            workers_total=workers_total,
        ),
    }


def compute_hq_grade_stats(db: Session, period: FunctionalEvalPeriod) -> dict[str, Any]:
    from app.modules.functional_eval.site_alias import parse_erp_site_team_prefix
    from app.modules.functional_eval.service import (
        _attendance_worker_payloads,
        _site_evaluator_map,
    )

    registry = _registry_rows(db)
    headcount_map = {reg.site_code: int(reg.erp_headcount or 0) for reg in registry}
    overall_erp_total = sum(headcount_map.values())

    payloads = _attendance_worker_payloads(db, period)
    evaluators = _site_evaluator_map(db, {reg.site_code for reg in registry})

    by_site_workers: dict[str, list[dict[str, Any]]] = {reg.site_code: [] for reg in registry}
    site_team_meta: dict[str, dict[str, Any]] = {}

    for reg in registry:
        code = reg.site_code
        site_name = reg.erp_site_label or f"현장 {code}"
        team_info = parse_erp_site_team_prefix(site_name)
        site_team_meta[code] = {
            "site_code": code,
            "site_name": site_name,
            "evaluator_name": evaluators.get(code) or "—",
            "erp_headcount": headcount_map.get(code, 0),
            **team_info,
        }

    for worker in payloads:
        code = str(worker.get("site_code") or "")
        if not code:
            continue
        if code not in by_site_workers:
            by_site_workers[code] = []
            if code not in site_team_meta:
                site_name = str(worker.get("site_name") or f"현장 {code}")
                site_team_meta[code] = {
                    "site_code": code,
                    "site_name": site_name,
                    "evaluator_name": evaluators.get(code) or "—",
                    "erp_headcount": headcount_map.get(code, 0),
                    **parse_erp_site_team_prefix(site_name),
                }
        by_site_workers[code].append(worker)

    site_items: list[dict[str, Any]] = []
    by_team_workers: dict[str, list[dict[str, Any]]] = {}
    team_erp_totals: dict[str, int] = {}

    for reg in registry:
        code = reg.site_code
        meta = site_team_meta[code]
        site_workers = by_site_workers.get(code, [])
        erp_total = headcount_map.get(code, 0)
        block = _grade_stats_block(site_workers, workers_total=erp_total)
        site_items.append({**meta, **block})

        team_key = str(meta.get("team_key") or "unknown")
        by_team_workers.setdefault(team_key, []).extend(site_workers)
        team_erp_totals[team_key] = team_erp_totals.get(team_key, 0) + erp_total

    team_items: list[dict[str, Any]] = []
    for team_key in sorted(by_team_workers.keys(), key=lambda k: (k == "unknown", k == "관급", k)):
        team_workers = by_team_workers[team_key]
        site_codes_in_team = sorted(
            {
                reg.site_code
                for reg in registry
                if str(site_team_meta.get(reg.site_code, {}).get("team_key") or "unknown") == team_key
            }
        )
        metas = [site_team_meta[code] for code in site_codes_in_team if code in site_team_meta]
        team_no = metas[0].get("team_no") if metas else None
        contractors = sorted({str(m.get("contractor_label") or "").strip() for m in metas if m.get("contractor_label")})
        if team_key == "관급":
            team_label = "관급"
        elif team_key == "unknown":
            team_label = "기타"
        elif team_no is not None:
            team_label = f"공사{team_no}팀"
        else:
            team_label = str(team_key)
        erp_total = team_erp_totals.get(team_key, 0)
        block = _grade_stats_block(team_workers, workers_total=erp_total)
        team_items.append(
            {
                "team_key": team_key,
                "team_no": team_no,
                "team_label": team_label,
                "contractor_label": contractors[0] if len(contractors) == 1 else None,
                "contractor_labels": contractors,
                "site_count": len(site_codes_in_team),
                "site_codes": site_codes_in_team,
                "erp_headcount": erp_total,
                **block,
            }
        )

    computed_at = utc_now()
    payload = {
        "period_id": period.id,
        "erp_headcount_total": overall_erp_total,
        "computed_at": computed_at.isoformat(),
        "computed_at_label": format_kst_datetime_short(computed_at),
        "overall": _grade_stats_block(payloads, workers_total=overall_erp_total),
        "by_site": site_items,
        "by_team": team_items,
    }
    return _finalize_grade_stats_payload(payload, period)


def rebuild_and_persist(db: Session, period: FunctionalEvalPeriod) -> dict[str, Any]:
    payload = compute_hq_grade_stats(db, period)
    payload["is_stale"] = False
    payload["stale_reason"] = None
    payload["stale_marked_at"] = None
    period.hq_grade_stats_json = payload
    period.hq_grade_stats_computed_at = utc_now()
    db.add(period)
    db.commit()
    db.refresh(period)
    return payload


def mark_dirty(db: Session, period: FunctionalEvalPeriod, *, reason: str = "source_changed") -> None:
    cached = period.hq_grade_stats_json
    if not isinstance(cached, dict) or not cached.get("overall"):
        return
    cached = dict(cached)
    cached["is_stale"] = True
    cached["stale_reason"] = reason
    cached["stale_marked_at"] = utc_now().isoformat()
    period.hq_grade_stats_json = cached
    db.add(period)
    db.commit()
    db.refresh(period)


def _cache_expired(period: FunctionalEvalPeriod) -> bool:
    computed_at = period.hq_grade_stats_computed_at
    if computed_at is None:
        return True
    return utc_now() - computed_at >= HQ_GRADE_STATS_CACHE_TTL


def get_hq_grade_stats(db: Session, period: FunctionalEvalPeriod) -> dict[str, Any]:
    expected_mode = _expected_grade_stats_mode(period)
    cached = period.hq_grade_stats_json
    if isinstance(cached, dict) and cached.get("overall"):
        if cached.get("grade_stats_mode") == expected_mode:
            if not _cache_expired(period):
                return cached
    return rebuild_and_persist(db, period)


def get_site_grade_stats(db: Session, period: FunctionalEvalPeriod, site_code: str) -> dict[str, Any]:
    code = (site_code or "").strip()
    cached = get_hq_grade_stats(db, period)
    for row in cached.get("by_site") or []:
        if str(row.get("site_code") or "") == code:
            return {
                "period_id": period.id,
                "site_code": code,
                "site_name": row.get("site_name"),
                "evaluator_name": row.get("evaluator_name"),
                "team_key": row.get("team_key"),
                "team_no": row.get("team_no"),
                "team_label": row.get("team_label"),
                "contractor_label": row.get("contractor_label"),
                "erp_headcount": row.get("erp_headcount"),
                "functional": row.get("functional"),
                "safety": row.get("safety"),
                "computed_at": cached.get("computed_at"),
                "computed_at_label": cached.get("computed_at_label"),
                "grade_stats_mode": cached.get("grade_stats_mode"),
                "grade_stats_mode_label": cached.get("grade_stats_mode_label"),
                "grade_stats_live_from": cached.get("grade_stats_live_from"),
            }
    raise ValueError("NO_SITE_IN_REGISTRY")
