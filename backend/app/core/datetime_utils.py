"""UTC 시각 헬퍼 (datetime.utcnow() Deprecation 대체, DB용 naive UTC 유지)."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
