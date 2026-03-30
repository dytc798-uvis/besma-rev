from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from app.modules.document_generation.constants import GenerationRule
from app.modules.document_settings.service import EffectiveRuleResult


@dataclass(frozen=True)
class GenerationSlot:
    period_start: date
    period_end: date
    generation_anchor_date: date


@dataclass(frozen=True)
class Period:
    start: date
    end: date


def resolve_period_for_cycle(cycle_code: str, as_of_date: date) -> Period | None:
    if cycle_code == "DAILY":
        return Period(start=as_of_date, end=as_of_date)
    if cycle_code == "WEEKLY":
        start = as_of_date - timedelta(days=as_of_date.weekday())
        return Period(start=start, end=start + timedelta(days=6))
    if cycle_code == "MONTHLY":
        return Period(start=_month_start(as_of_date), end=_month_end(as_of_date))
    if cycle_code == "QUARTERLY":
        return Period(start=_quarter_start(as_of_date), end=_quarter_end(as_of_date))
    if cycle_code == "HALF_YEARLY":
        return Period(start=_half_year_start(as_of_date), end=_half_year_end(as_of_date))
    if cycle_code == "YEARLY":
        return Period(start=_year_start(as_of_date), end=_year_end(as_of_date))
    return None


def anchor_on_day_of_period(period: Period, requested_day: int) -> date:
    """
    ON_DAY_OF_PERIOD 규칙의 기준일(anchor) 계산.
    - requested_day는 1-based.
    - calendar day가 아닌 "period 내 N번째 날"로 계산한다.
    - 반드시 period.start <= anchor <= period.end를 보장한다.
    """
    if requested_day <= 1:
        return period.start

    total_days = (period.end - period.start).days + 1
    actual_day = min(requested_day, total_days)
    anchor = period.start + timedelta(days=actual_day - 1)

    if anchor < period.start:
        return period.start
    if anchor > period.end:
        return period.end
    return anchor


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    return d.replace(day=monthrange(d.year, d.month)[1])


def _quarter_start(d: date) -> date:
    month = ((d.month - 1) // 3) * 3 + 1
    return date(d.year, month, 1)


def _quarter_end(d: date) -> date:
    start = _quarter_start(d)
    end_month = start.month + 2
    return date(start.year, end_month, monthrange(start.year, end_month)[1])


def _half_year_start(d: date) -> date:
    return date(d.year, 1 if d.month <= 6 else 7, 1)


def _half_year_end(d: date) -> date:
    month = 6 if d.month <= 6 else 12
    return date(d.year, month, monthrange(d.year, month)[1])


def _year_start(d: date) -> date:
    return date(d.year, 1, 1)


def _year_end(d: date) -> date:
    return date(d.year, 12, 31)


def resolve_generation_slot(rule: EffectiveRuleResult, as_of_date: date) -> GenerationSlot | None:
    if not rule.is_required:
        return None
    if rule.cycle is None:
        return None

    period = resolve_period_for_cycle(rule.cycle, as_of_date)
    if not period:
        return None
    period_start = period.start
    period_end = period.end

    if rule.generation_rule in {None, GenerationRule.ON_PERIOD_START, GenerationRule.DAILY}:
        anchor = period_start
    elif rule.generation_rule == GenerationRule.ON_PERIOD_END:
        anchor = period_end
    elif rule.generation_rule == GenerationRule.ON_DAY_OF_PERIOD:
        if rule.generation_value is None or str(rule.generation_value).strip() == "":
            anchor = period_start
        else:
            requested_day = max(1, int(rule.generation_value))
            anchor = anchor_on_day_of_period(period, requested_day)
    else:
        anchor = period_start

    return GenerationSlot(
        period_start=period_start,
        period_end=period_end,
        generation_anchor_date=anchor,
    )


def resolve_due_date(slot: GenerationSlot, due_offset_days: int | None) -> date:
    offset = due_offset_days or 0
    return slot.generation_anchor_date + timedelta(days=offset)
