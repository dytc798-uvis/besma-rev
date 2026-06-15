"""기능인제 평가 시행 일정 (KST)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

_KST = timezone(timedelta(hours=9), name="KST")

# 2026년 6월 1차 시행 — 마감·오픈 시각 (KST)
EVAL_CAMPAIGN_DEADLINE = date(2026, 6, 30)
EVAL_OPEN_DATE_KST = date(2026, 6, 16)
EVAL_OPEN_TIME_KST = time(6, 0)


def evaluation_open_at_kst() -> datetime:
    return datetime.combine(EVAL_OPEN_DATE_KST, EVAL_OPEN_TIME_KST, tzinfo=_KST)


def evaluation_is_open(*, at: datetime | None = None) -> bool:
    ref = at if at is not None else datetime.now(_KST)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=_KST)
    else:
        ref = ref.astimezone(_KST)
    return ref >= evaluation_open_at_kst()


def assert_evaluation_open() -> None:
    if not evaluation_is_open():
        raise ValueError("EVAL_NOT_OPEN")


def evaluation_opens_at_kst_iso() -> str:
    return evaluation_open_at_kst().isoformat()


def evaluation_opens_at_kst_label() -> str:
    return f"{EVAL_OPEN_DATE_KST.year}년 {EVAL_OPEN_DATE_KST.month}월 {EVAL_OPEN_DATE_KST.day}일 오전 6시"
