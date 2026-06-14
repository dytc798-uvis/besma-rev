"""UTC 시각 헬퍼 (datetime.utcnow() Deprecation 대체, DB용 naive UTC 유지)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9), name="KST")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def kst_today() -> date:
    """한국 현장 기준 '오늘' 날짜(서버 OS 타임존과 무관)."""
    return datetime.now(_KST).date()


def kst_midnight_utc_naive(*, on_date: date | None = None) -> datetime:
    """한국 날짜 자정(KST)을 DB용 naive UTC datetime으로 반환."""
    d = on_date if on_date is not None else kst_today()
    kst_midnight = datetime.combine(d, datetime.min.time(), tzinfo=_KST)
    return kst_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_naive_to_kst(dt: datetime) -> datetime:
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return aware.astimezone(_KST)


def format_kst_datetime_short(dt: datetime | None) -> str:
    """예: 2026-06-14 17:09 (DB naive UTC → KST)."""
    if dt is None:
        return ""
    return _utc_naive_to_kst(dt).strftime("%Y-%m-%d %H:%M")


def format_kst_datetime_label(dt: datetime | None) -> str:
    """예: 2026년 6월 14일 오후 1시 29분 (DB naive UTC → KST)."""
    if dt is None:
        return ""
    kst = _utc_naive_to_kst(dt)
    hour = kst.hour
    minute = kst.minute
    if hour < 12:
        ampm = "오전"
        display_hour = 12 if hour == 0 else hour
    else:
        ampm = "오후"
        display_hour = 12 if hour == 12 else hour - 12
    return f"{kst.year}년 {kst.month}월 {kst.day}일 {ampm} {display_hour}시 {minute}분"
