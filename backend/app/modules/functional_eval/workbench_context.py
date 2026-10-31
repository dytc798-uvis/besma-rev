"""Evaluation navigation metadata. No period creation, completion lock or intake."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import unicodedata

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import MetaData, Table, case, exists, func, inspect, or_, select

from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep, assert_fe_hq_read
from app.modules.sites.models import Site
from .models import (FunctionalEvalPeriod as Period, FunctionalEvalWorker as Worker,
                     FunctionalEvalAssessment as Assessment, FunctionalEvalAttendanceEntry as Attendance)

router = APIRouter()
SCHEMA = "jsi.functional-eval-workbench-context.v1"
ADDITIONAL_TABLES = frozenset({"functional_eval_additional_approvals", "functional_eval_target_enrollments",
                              "functional_eval_period_modes", "functional_eval_intake_receipts"})


def _invalid():
    return HTTPException(409, "평가기간·현장 정보를 확인해야 합니다.")


def _text(value, maximum):
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
        raise _invalid()
    if any(unicodedata.category(c) == "Cc" for c in value):
        raise _invalid()
    return value


def read_context(db):
    # This guard also prevents ORM autoflush if a caller has unrelated pending state.
    with db.no_autoflush:
        periods = db.query(Period.id, Period.deadline_date).filter(Period.is_active.is_(True)).limit(2).all()
        if not periods:
            raise HTTPException(404, "등록된 평가기간이 없습니다.")
        if len(periods) != 1:
            raise _invalid()
        period_id, deadline = periods[0]
        if not isinstance(period_id, int) or not 1 <= period_id <= 999999999 or not isinstance(deadline, date):
            raise _invalid()

        # Optional tables are inspected on this request's connection, never migrated.
        connection = db.connection()
        present = ADDITIONAL_TABLES.intersection(inspect(connection).get_table_names())
        if present and present != ADDITIONAL_TABLES:
            raise _invalid()
        mode, enrollment = "PERIODIC", None
        if present:
            metadata = MetaData()
            modes = Table("functional_eval_period_modes", metadata, autoload_with=connection)
            enrollment = Table("functional_eval_target_enrollments", metadata, autoload_with=connection)
            records = db.execute(select(modes.c.mode).where(modes.c.period_id == period_id)).scalars().all()
            if len(records) > 1 or records and records[0] not in {"PERIODIC", "CONTINUOUS"}:
                raise _invalid()
            mode = records[0] if records else "PERIODIC"
            if not hasattr(Worker, "evaluation_batch"):
                raise _invalid()

        attended = exists(select(Attendance.id).where(Attendance.period_id == period_id,
                                                       Attendance.rrn_hash == Worker.rrn_hash))
        assessed = exists(select(Assessment.id).where(Assessment.worker_id == Worker.id))
        eligible = [attended, assessed]
        if enrollment is not None:
            eligible.append(exists(select(enrollment.c.worker_id).where(
                enrollment.c.period_id == period_id, enrollment.c.worker_id == Worker.id)))
        query = db.query(Worker.site_code).filter(Worker.period_id == period_id,
                    Worker.is_site_manager.is_(False), or_(*eligible))
        if enrollment is not None:
            # Match existing current-round policy without creating approval/completion locks.
            other = Worker.__table__.alias("context_enrolled_worker")
            enrolled_batches = (select(func.max(enrollment.c.evaluation_batch)).select_from(enrollment.join(
                other, enrollment.c.worker_id == other.c.id)).where(
                    enrollment.c.period_id == period_id, other.c.site_code == Worker.site_code)
                .correlate(Worker).scalar_subquery())
            observed = Worker.__table__.alias("context_observed_worker")
            has_attendance = exists(select(Attendance.id).where(
                Attendance.period_id == period_id, Attendance.rrn_hash == observed.c.rrn_hash))
            has_assessment = exists(select(Assessment.id).where(Assessment.worker_id == observed.c.id))
            observed_batches = (select(func.max(observed.c.evaluation_batch)).where(
                observed.c.period_id == period_id, observed.c.site_code == Worker.site_code,
                observed.c.is_site_manager.is_(False), or_(has_attendance, has_assessment))
                .correlate(Worker).scalar_subquery())
            enrolled_batch, observed_batch = func.coalesce(enrolled_batches, 0), func.coalesce(observed_batches, 0)
            batches = case((enrolled_batch > observed_batch, enrolled_batch), else_=observed_batch)
            query = query.filter(or_(func.coalesce(batches, 0) == 0,
                                      func.coalesce(Worker.evaluation_batch, 0) == batches))
        # Count the same existing/current-round eligible workers, never today's
        # attendance rows or a claim of complete all-worker coverage.
        counts = {_text(code, 100): count for code, count in query.with_entities(
            Worker.site_code, func.count(Worker.id)).group_by(Worker.site_code).all()}
        if any(not isinstance(count, int) or not 1 <= count <= 1000000 for count in counts.values()):
            raise _invalid()
        codes = set(counts)
        if len(codes) > 10000:
            raise _invalid()
        registered = dict(db.query(Site.site_code, Site.site_name).filter(Site.site_code.in_(codes)).all()) if codes else {}
        labels = {}
        # Scalar columns only: no names, phone numbers, identity hashes, scores or signatures are read into payloads.
        rows = db.query(Attendance.site_code, Attendance.erp_site_label).filter(
            Attendance.period_id == period_id, Attendance.site_code.in_(codes)).order_by(Attendance.id).all() if codes else []
        for code, label in rows:
            text = (label or "").strip()
            if text.startswith("현장명:"):
                text = text.split(":", 1)[1].strip()
            if text and len(text) > len(labels.get(code, "")):
                labels[code] = text
        sites = [{"site_code": code, "site_name": _text(labels.get(code) or (registered.get(code) or "").strip() or f"현장 {code}", 300),
                  "evaluation_target_count": counts[code]}
                 for code in sorted(codes)]
        today = datetime.now(timezone(timedelta(hours=9))).date()
        return {"schema": SCHEMA, "read_only": True,
                "period": {"id": period_id, "deadline_date": None if mode == "CONTINUOUS" else deadline.isoformat(),
                           "evaluation_mode": mode, "is_closed": False if mode == "CONTINUOUS" else today > deadline},
                "sites": sites}


@router.get("/hq/workbench-context")
def workbench_context(db: DbDep, user: CurrentUserDep, response: Response):
    assert_fe_hq_read(user)
    response.headers["Cache-Control"] = "no-store"
    return read_context(db)
