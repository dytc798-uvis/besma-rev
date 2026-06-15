"""기능인인정제 일일 진행현황 보고서 — 집계·생성·저장."""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.datetime_utils import format_kst_datetime_label, kst_today, utc_now
from app.core.enums import Role
from app.modules.functional_eval import approval_workflow, service, signature_ops
from app.modules.functional_eval.constants import (
    APPROVAL_STATUS_CEO_APPROVED,
    APPROVAL_STATUS_HQ_APPROVED,
    APPROVAL_STATUS_HQ_OFFICER_APPROVED,
    APPROVAL_STATUS_IN_PROGRESS,
    APPROVAL_STATUS_LABELS,
    APPROVAL_STATUS_REJECTED,
    APPROVAL_STATUS_SITE_APPROVED,
)
from app.modules.functional_eval.daily_report_pdf import generate_daily_report_pdf
from app.modules.functional_eval.grade_inflation_guard import compute_grade_inflation_review
from app.modules.functional_eval.models import (
    FunctionalEvalCustomerReward,
    FunctionalEvalDailyReport,
    FunctionalEvalPeriod,
    FunctionalEvalSanction,
    FunctionalEvalSignature,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.signature_service import STAGE_TEAM_LEADER, batch_label
from app.modules.users.models import User

logger = logging.getLogger(__name__)

REPORT_TITLE = "기능인인정제 일일 진행현황 보고서"
KST = timezone(timedelta(hours=9), name="KST")

# 향후 알림 예시:
# [기능인인정제 일일보고] 2026-06-16 기준 전체 128명 중 73명 평가완료(57.0%). 미완료 현장 4개, 소장 제출 대기 2개.


def criteria_at_kst_label(report_date: date) -> str:
    return f"{report_date.isoformat()} 21:00 KST"


def kst_day_utc_range(report_date: date) -> tuple[datetime, datetime]:
    """KST 하루 구간을 DB naive UTC로."""
    start_kst = datetime.combine(report_date, datetime.min.time(), tzinfo=KST)
    end_kst = start_kst + timedelta(days=1)
    return (
        start_kst.astimezone(timezone.utc).replace(tzinfo=None),
        end_kst.astimezone(timezone.utc).replace(tzinfo=None),
    )


def daily_report_storage_dir(report_date: date) -> Path:
    root = settings.storage_root / "functional_eval" / "daily_reports" / f"{report_date.year:04d}" / f"{report_date.month:02d}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def report_file_stem(report_date: date) -> str:
    return f"functional_eval_daily_report_{report_date.strftime('%Y%m%d')}"


def resolve_report_path(stored: str | None) -> Path | None:
    if not stored:
        return None
    p = Path(stored)
    if p.is_file():
        return p
    alt = settings.storage_root / stored
    return alt if alt.is_file() else None


def _approval_flags(status: str) -> dict[str, bool]:
    return {
        "site_submitted": status
        in {
            APPROVAL_STATUS_SITE_APPROVED,
            APPROVAL_STATUS_HQ_OFFICER_APPROVED,
            APPROVAL_STATUS_HQ_APPROVED,
            APPROVAL_STATUS_CEO_APPROVED,
        },
        "hq_officer_approved": status
        in {APPROVAL_STATUS_HQ_OFFICER_APPROVED, APPROVAL_STATUS_HQ_APPROVED, APPROVAL_STATUS_CEO_APPROVED},
        "hq_director_approved": status in {APPROVAL_STATUS_HQ_APPROVED, APPROVAL_STATUS_CEO_APPROVED},
        "ceo_approved": status == APPROVAL_STATUS_CEO_APPROVED,
    }


def _site_current_stage(
    *,
    total: int,
    complete: int,
    approval_status: str,
    team_signed: int,
    team_required: int,
) -> str:
    if total <= 0:
        return "출역 대상 없음"
    if complete < total:
        return "평가 진행"
    if team_required > 0 and team_signed < team_required:
        return "팀장 평가완료보고서 서명"
    if approval_status in {APPROVAL_STATUS_IN_PROGRESS, APPROVAL_STATUS_REJECTED}:
        return "소장 최종 제출 대기"
    return APPROVAL_STATUS_LABELS.get(approval_status, approval_status)


def _count_approval_sites(db: Session, period_id: int) -> dict[str, int]:
    from app.modules.functional_eval.models import FunctionalEvalSiteApproval

    rows = db.query(FunctionalEvalSiteApproval).filter(FunctionalEvalSiteApproval.period_id == period_id).all()
    site_submitted = hq_officer = hq_director = ceo = 0
    for row in rows:
        flags = _approval_flags(row.status)
        if flags["site_submitted"]:
            site_submitted += 1
        if flags["hq_officer_approved"]:
            hq_officer += 1
        if flags["hq_director_approved"]:
            hq_director += 1
        if flags["ceo_approved"]:
            ceo += 1
    return {
        "site_submitted_count": site_submitted,
        "hq_officer_approved_count": hq_officer,
        "hq_director_approved_count": hq_director,
        "ceo_approved_count": ceo,
    }


def _team_signoff_counts(db: Session, period: FunctionalEvalPeriod, site_code: str, batch: int) -> tuple[int, int]:
    leaders = signature_ops.list_team_leader_report_status(db, period, site_code, batch=batch)
    required = len(leaders)
    signed = sum(1 for row in leaders if row.get("team_leader_signed"))
    return signed, required


def _evaluator_rows(
    db: Session,
    period: FunctionalEvalPeriod,
    workers: list[FunctionalEvalWorker],
    assess_map: dict[int, dict],
) -> list[dict[str, Any]]:
    from app.modules.users.models import User as UserModel

    users_by_login = {
        (u.login_id or "").strip(): u
        for u in db.query(UserModel).filter(UserModel.role == Role.SITE_FUNCTIONAL_EVAL).all()
    }
    site_names = service._site_name_map(db, {w.site_code for w in workers if w.site_code})

    buckets: dict[str, dict[str, Any]] = {}
    for worker in workers:
        login = (worker.assigned_evaluator_login_id or "").strip()
        if not login:
            login = service._manager_login_for_site(db, worker.site_code) or "—"
        if login not in buckets:
            user = users_by_login.get(login)
            buckets[login] = {
                "site_code": worker.site_code,
                "site_name": site_names.get(worker.site_code or "", worker.site_code or "—"),
                "login_id": login,
                "name": (user.name if user else login) or login,
                "role": "소장" if user and service._is_manager_user_for_site(db, user, worker.site_code) else "팀장",
                "assigned": 0,
                "completed": 0,
                "incomplete_workers": [],
            }
        payload = service._worker_assess_payload(assess_map, worker.id)
        buckets[login]["assigned"] += 1
        if service._is_fully_evaluated(payload):
            buckets[login]["completed"] += 1
        else:
            buckets[login]["incomplete_workers"].append(worker.name)

    rows: list[dict[str, Any]] = []
    for row in buckets.values():
        assigned = row["assigned"]
        completed = row["completed"]
        batch = 0
        signed, _required = _team_signoff_counts(db, period, row["site_code"] or "", batch)
        team_sig = (
            db.query(FunctionalEvalSignature)
            .filter(
                FunctionalEvalSignature.period_id == period.id,
                FunctionalEvalSignature.stage == STAGE_TEAM_LEADER,
                FunctionalEvalSignature.signer_login_id == row["login_id"],
                FunctionalEvalSignature.evaluation_batch == batch,
            )
            .first()
        )
        rows.append(
            {
                **row,
                "incomplete_count": assigned - completed,
                "completion_rate_pct": round(100.0 * completed / assigned, 1) if assigned else 0.0,
                "signoff_complete": team_sig is not None,
                "incomplete_worker_names": row["incomplete_workers"][:20],
                "incomplete_worker_overflow": max(0, len(row["incomplete_workers"]) - 20),
            }
        )
    rows.sort(key=lambda r: (r["site_code"], 0 if r["role"] == "소장" else 1, r["login_id"]))
    return rows


def _grade_block_for_workers(worker_payloads: list[dict[str, Any]], *, site_code: str | None = None) -> dict[str, Any]:
    functional_review = compute_grade_inflation_review(worker_payloads)
    safety_stats = service._grade_distribution(worker_payloads, assessment_field="safety_assessment")
    functional_stats = functional_review.get("grade_stats", {}).get("functional") or service._grade_distribution(
        worker_payloads, assessment_field="functional_assessment"
    )
    s_over = bool(functional_review.get("s_over_limit"))
    return {
        "site_code": site_code,
        "functional": {
            **functional_stats,
            "s_over_20pct": s_over,
            "s_over_limit_reason_provided": False,
            "note": "기능/품질(2-1) S등급 20% 초과 시 사유 입력 필요",
        },
        "safety": {
            **safety_stats,
            "note": "안전(2-2)은 S 20% 제한 없음 · 제재/지적 이력 기반 감점형",
        },
    }


def _reward_sanction_day_stats(db: Session, period: FunctionalEvalPeriod, report_date: date) -> dict[str, Any]:
    start_utc, end_utc = kst_day_utc_range(report_date)
    sanctions = (
        db.query(FunctionalEvalSanction)
        .filter(
            FunctionalEvalSanction.period_id == period.id,
            FunctionalEvalSanction.created_at >= start_utc,
            FunctionalEvalSanction.created_at < end_utc,
        )
        .all()
    )
    rewards = (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.period_id == period.id,
            FunctionalEvalCustomerReward.created_at >= start_utc,
            FunctionalEvalCustomerReward.created_at < end_utc,
        )
        .all()
    )
    sanction_by_site: Counter[str] = Counter()
    reward_by_site: Counter[str] = Counter()
    sanction_by_type: Counter[str] = Counter()
    repeat_workers: set[int] = set()
    worker_strikes: Counter[int] = Counter()
    for s in sanctions:
        sanction_by_site[s.site_code] += 1
        sanction_by_type[s.violation_code] += 1
        worker_strikes[s.worker_id] += 1
        if s.strike_number and s.strike_number > 1:
            repeat_workers.add(s.worker_id)
    for r in rewards:
        reward_by_site[r.site_code] += 1
    return {
        "report_date": report_date.isoformat(),
        "reward_count": len(rewards),
        "sanction_count": len(sanctions),
        "reward_by_site": dict(reward_by_site),
        "sanction_by_site": dict(sanction_by_site),
        "sanction_by_violation": dict(sanction_by_type),
        "repeat_sanction_worker_count": len(repeat_workers),
        "penalty_applied_count": sum(1 for s in sanctions if (s.penalty_points or 0) > 0),
    }


def _supplemental_eval_stats(db: Session, period: FunctionalEvalPeriod, workers: list[FunctionalEvalWorker]) -> dict[str, Any]:
    by_site: dict[str, dict[str, Any]] = {}
    for w in workers:
        batch = w.evaluation_batch or 0
        if batch <= 0:
            continue
        code = w.site_code or ""
        if code not in by_site:
            by_site[code] = {
                "site_code": code,
                "batch": batch,
                "batch_label": batch_label(batch),
                "target_count": 0,
                "completed_count": 0,
                "signoff_complete": False,
                "ui_note": "추가평가 전용 UI는 후속 보완 예정",
            }
        by_site[code]["target_count"] += 1
    assess_map = service._assessments_map(db, [w.id for w in workers if (w.evaluation_batch or 0) > 0])
    for w in workers:
        if (w.evaluation_batch or 0) <= 0:
            continue
        code = w.site_code or ""
        if service._is_fully_evaluated(service._worker_assess_payload(assess_map, w.id)):
            by_site[code]["completed_count"] += 1
    sites = list(by_site.values())
    return {
        "has_supplemental_batch": bool(sites),
        "sites": sites,
        "ui_followup_note": "추가평가 전용 UI는 후속 보완 예정",
    }


def build_daily_report_snapshot(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    report_date: date | None = None,
) -> dict[str, Any]:
    report_date = report_date or kst_today()
    overview = service.build_hq_sites_overview(db, period)
    workers = service._attendance_target_workers(db, period)
    assess_map = service._assessments_map(db, [w.id for w in workers])
    worker_payloads = service._attendance_worker_payloads(db, period)
    approval_counts = _count_approval_sites(db, period.id)

    team_signoff_total = (
        db.query(FunctionalEvalSignature)
        .filter(
            FunctionalEvalSignature.period_id == period.id,
            FunctionalEvalSignature.stage == STAGE_TEAM_LEADER,
        )
        .count()
    )

    site_rows: list[dict[str, Any]] = []
    for site in overview.get("sites") or []:
        code = site.get("site_code") or ""
        batch = max(signature_ops.active_site_batches(db, period, code) or [0])
        team_signed, team_required = _team_signoff_counts(db, period, code, batch)
        approval = approval_workflow.get_or_create_site_approval(db, period.id, code)
        flags = _approval_flags(approval.status)
        summary = service.serialize_site_approval_summary(db, period, code)
        site_workers = [p for p in worker_payloads if (p.get("site_code") or p.get("worker", {}).get("site_code")) == code]
        if not site_workers:
            site_workers = [p for p in worker_payloads if str(p.get("site_code")) == code]
        grade_review = compute_grade_inflation_review(
            service.site_worker_payloads_for_batch(db, period, code, batch)
        )
        site_rows.append(
            {
                "site_code": code,
                "site_name": site.get("site_name") or code,
                "total_workers": int(site.get("total") or 0),
                "completed_workers": int(site.get("fully_complete") or 0),
                "incomplete_workers": int(site.get("total") or 0) - int(site.get("fully_complete") or 0),
                "completion_rate_pct": float(site.get("progress_pct") or 0),
                "team_leader_signed": team_signed,
                "team_leader_required": team_required,
                **flags,
                "current_stage": _site_current_stage(
                    total=int(site.get("total") or 0),
                    complete=int(site.get("fully_complete") or 0),
                    approval_status=approval.status,
                    team_signed=team_signed,
                    team_required=team_required,
                ),
                "functional_s_over_20pct": bool(grade_review.get("s_over_limit")),
                "note": site.get("evaluator_missing") and "평가자 계정 미등록" or "",
            }
        )

    evaluator_rows = _evaluator_rows(db, period, workers, assess_map)
    grade_overall = _grade_block_for_workers(worker_payloads)
    grade_by_site = [
        _grade_block_for_workers(
            service.site_worker_payloads_for_batch(db, period, row["site_code"], max(signature_ops.active_site_batches(db, period, row["site_code"]) or [0])),
            site_code=row["site_code"],
        )
        for row in site_rows
        if row["total_workers"] > 0
    ]

    reward_sanction = _reward_sanction_day_stats(db, period, report_date)
    supplemental = _supplemental_eval_stats(db, period, workers)

    bottlenecks: dict[str, list[dict[str, Any]]] = {
        "low_completion_sites": [],
        "high_incomplete_sites": [],
        "team_signoff_pending_sites": [],
        "site_submit_pending_sites": [],
        "hq_officer_pending_sites": [],
        "hq_director_pending_sites": [],
        "ceo_pending_sites": [],
        "functional_s_over_sites": [],
        "supplemental_batch_sites": [],
    }
    for row in site_rows:
        code = row["site_code"]
        name = row["site_name"]
        if row["total_workers"] > 0 and row["completion_rate_pct"] < 50:
            bottlenecks["low_completion_sites"].append({"site_code": code, "site_name": name, "rate_pct": row["completion_rate_pct"]})
        if row["incomplete_workers"] >= 5:
            bottlenecks["high_incomplete_sites"].append({"site_code": code, "site_name": name, "incomplete": row["incomplete_workers"]})
        if row["team_leader_required"] > row["team_leader_signed"]:
            bottlenecks["team_signoff_pending_sites"].append({"site_code": code, "site_name": name})
        if row["completed_workers"] == row["total_workers"] and row["total_workers"] > 0 and not row["site_submitted"]:
            bottlenecks["site_submit_pending_sites"].append({"site_code": code, "site_name": name})
        approval = approval_workflow.get_or_create_site_approval(db, period.id, code)
        if approval.status == APPROVAL_STATUS_SITE_APPROVED:
            bottlenecks["hq_officer_pending_sites"].append({"site_code": code, "site_name": name})
        if approval.status == APPROVAL_STATUS_HQ_OFFICER_APPROVED:
            bottlenecks["hq_director_pending_sites"].append({"site_code": code, "site_name": name})
        if approval.status == APPROVAL_STATUS_HQ_APPROVED:
            bottlenecks["ceo_pending_sites"].append({"site_code": code, "site_name": name})
        if row.get("functional_s_over_20pct"):
            bottlenecks["functional_s_over_sites"].append({"site_code": code, "site_name": name})
    for s in supplemental.get("sites") or []:
        bottlenecks["supplemental_batch_sites"].append(s)

    totals = overview.get("totals") or {}
    total_workers = int(totals.get("workers") or 0)
    completed_workers = int(totals.get("fully_complete") or 0)
    completion_rate = round(100.0 * completed_workers / total_workers, 1) if total_workers else 0.0
    bottleneck_site_count = len(
        {
            item["site_code"]
            for key, items in bottlenecks.items()
            if key != "supplemental_batch_sites"
            for item in items
        }
    )

    return {
        "title": REPORT_TITLE,
        "report_date": report_date.isoformat(),
        "criteria_at_kst": criteria_at_kst_label(report_date),
        "timezone": "Asia/Seoul",
        "period": overview.get("period"),
        "summary": {
            "total_workers": total_workers,
            "completed_workers": completed_workers,
            "incomplete_workers": total_workers - completed_workers,
            "completion_rate_pct": completion_rate,
            "team_signoff_signature_count": team_signoff_total,
            **approval_counts,
        },
        "sites": site_rows,
        "evaluators": evaluator_rows,
        "grade_distribution": {"overall": grade_overall, "by_site": grade_by_site},
        "reward_sanction": reward_sanction,
        "bottlenecks": bottlenecks,
        "bottleneck_site_count": bottleneck_site_count,
        "supplemental_eval": supplemental,
        "generated_note": "본 보고서는 기능인인정제 시스템의 평가·서명·승인 데이터를 기준으로 자동 생성되었습니다.",
    }


def serialize_daily_report_row(row: FunctionalEvalDailyReport) -> dict[str, Any]:
    return {
        "id": row.id,
        "report_date": row.report_date.isoformat(),
        "criteria_at_kst": row.criteria_at_kst,
        "generated_at": row.generated_at.isoformat(),
        "generated_at_label": format_kst_datetime_label(row.generated_at),
        "regenerated_at": row.regenerated_at.isoformat() if row.regenerated_at else None,
        "total_workers": row.total_workers,
        "completed_workers": row.completed_workers,
        "completion_rate_pct": row.completion_rate,
        "bottleneck_site_count": row.bottleneck_site_count,
        "generated_by": row.generated_by,
        "version": row.version,
        "has_document": bool(row.report_path),
    }


def list_daily_reports(db: Session, period: FunctionalEvalPeriod, *, limit: int = 30) -> list[dict[str, Any]]:
    rows = (
        db.query(FunctionalEvalDailyReport)
        .filter(FunctionalEvalDailyReport.period_id == period.id)
        .order_by(FunctionalEvalDailyReport.report_date.desc(), FunctionalEvalDailyReport.id.desc())
        .limit(limit)
        .all()
    )
    return [serialize_daily_report_row(r) for r in rows]


def get_daily_report(db: Session, report_id: int) -> FunctionalEvalDailyReport | None:
    return db.query(FunctionalEvalDailyReport).filter(FunctionalEvalDailyReport.id == report_id).first()


def _sanitize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _json_default(obj: Any):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"not serializable: {type(obj)}")


def _save_report_files(snapshot: dict[str, Any], report_date: date) -> tuple[str, str]:
    clean = _sanitize_for_json(snapshot)
    out_dir = daily_report_storage_dir(report_date)
    stem = report_file_stem(report_date)
    json_path = out_dir / f"{stem}.json"
    pdf_path = out_dir / f"{stem}.pdf"
    json_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    pdf_bytes = generate_daily_report_pdf(clean)
    pdf_path.write_bytes(pdf_bytes)
    return str(pdf_path), str(json_path)


def generate_daily_report(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    report_date: date | None = None,
    generated_by: str = "system",
    force: bool = False,
) -> FunctionalEvalDailyReport:
    report_date = report_date or kst_today()
    existing = (
        db.query(FunctionalEvalDailyReport)
        .filter(
            FunctionalEvalDailyReport.period_id == period.id,
            FunctionalEvalDailyReport.report_date == report_date,
        )
        .first()
    )
    if existing and not force and generated_by == "system":
        logger.info(
            "daily_report_skip_duplicate date=%s period_id=%s existing_id=%s",
            report_date,
            period.id,
            existing.id,
        )
        return existing

    snapshot = build_daily_report_snapshot(db, period, report_date=report_date)
    now = utc_now()
    next_version = (existing.version + 1) if (existing and force) else 1
    snapshot["meta"] = {
        "generated_at": now.isoformat(),
        "generated_at_label": format_kst_datetime_label(now),
        "generated_by": generated_by,
        "version": next_version,
    }
    clean = _sanitize_for_json(snapshot)
    pdf_path, json_path = _save_report_files(clean, report_date)
    summary = snapshot["summary"]
    bottleneck_site_count = int(snapshot.get("bottleneck_site_count") or 0)
    completion_rate = float(summary.get("completion_rate_pct") or 0)

    if existing and force:
        existing.generated_at = now
        existing.regenerated_at = now
        existing.version = (existing.version or 1) + 1
        existing.generated_by = generated_by
        existing.total_workers = int(summary.get("total_workers") or 0)
        existing.completed_workers = int(summary.get("completed_workers") or 0)
        existing.completion_rate = completion_rate
        existing.bottleneck_site_count = bottleneck_site_count
        existing.report_path = pdf_path
        existing.report_json_path = json_path
        existing.report_json_snapshot = clean
        db.commit()
        db.refresh(existing)
        row = existing
    elif existing:
        raise ValueError("REPORT_ALREADY_EXISTS")
    else:
        row = FunctionalEvalDailyReport(
            period_id=period.id,
            report_date=report_date,
            criteria_at_kst=criteria_at_kst_label(report_date),
            timezone="Asia/Seoul",
            generated_at=now,
            regenerated_at=now if generated_by == "manual" else None,
            total_workers=int(summary.get("total_workers") or 0),
            completed_workers=int(summary.get("completed_workers") or 0),
            completion_rate=completion_rate,
            bottleneck_site_count=bottleneck_site_count,
            report_path=pdf_path,
            report_json_path=json_path,
            report_format="pdf",
            report_json_snapshot=clean,
            generated_by=generated_by,
            version=1,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    logger.info(
        "daily_report_generated success date=%s path=%s completion_rate=%.1f bottleneck_sites=%d generated_by=%s version=%d",
        report_date,
        pdf_path,
        completion_rate,
        bottleneck_site_count,
        generated_by,
        row.version,
    )
    return row


def assert_hq_report_admin(user: User) -> None:
    if user.role not in {Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN}:
        raise ValueError("HQ_ADMIN_ONLY")
