"""UTC 시각 헬퍼 (datetime.utcnow() Deprecation 대체, DB용 naive UTC 유지)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def kst_today() -> date:
    """한국 현장 기준 '오늘' 날짜(서버 OS 타임존과 무관)."""
    return datetime.now(ZoneInfo("Asia/Seoul")).date()
