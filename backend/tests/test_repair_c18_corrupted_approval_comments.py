from __future__ import annotations

import random
from datetime import date, datetime

import pytest

from scripts.backfill_c18_approval_comments import RAIN_MM_BY_DATE
from scripts.repair_c18_corrupted_approval_comments import (
    CHEONGNA_RAIN_MM_BY_DATE,
    EXPECTED_INITIAL_TARGETS,
    MANAGER_REQUIREMENT_CODE,
    _choose_reply_at,
    _is_lunch_kst,
    _pick_hq_comment,
    _pick_site_reply,
    _validate_target_count,
)


def test_repair_uses_an_independent_copy_of_reviewed_cheongna_rain_dates():
    assert CHEONGNA_RAIN_MM_BY_DATE == RAIN_MM_BY_DATE
    assert CHEONGNA_RAIN_MM_BY_DATE is not RAIN_MM_BY_DATE
    assert CHEONGNA_RAIN_MM_BY_DATE[date(2026, 5, 20)] == 49.1


def test_reply_time_is_deterministic_after_approval_and_outside_kst_lunch():
    # 02:25 UTC = 11:25 KST. Every normal 5-35 minute candidate enters
    # lunch, so the helper must move the reply to a safe post-lunch time.
    approval_at = datetime(2026, 5, 20, 2, 25, 0)
    cutoff = datetime(2026, 5, 20, 8, 0, 0)

    first = _choose_reply_at(approval_at=approval_at, cutoff=cutoff, rng=random.Random(17))
    second = _choose_reply_at(approval_at=approval_at, cutoff=cutoff, rng=random.Random(17))

    assert first == second
    assert approval_at < first <= cutoff
    assert not _is_lunch_kst(first)


def test_rain_manager_text_and_reply_are_contextual_and_not_corrupted():
    hq_text = _pick_hq_comment(
        requirement_code=MANAGER_REQUIREMENT_CODE,
        rain_mm=1.0,
        rng=random.Random(3),
    )
    reply = _pick_site_reply(
        requirement_code=MANAGER_REQUIREMENT_CODE,
        rain_mm=1.0,
        rng=random.Random(3),
    )

    assert "??" not in hq_text
    assert "점검" in hq_text
    assert "빗물" in hq_text or "우천" in hq_text
    assert reply.startswith("네")
    assert "조치" in reply or "확인" in reply


def test_target_count_guard_allows_first_run_and_idempotent_zero_only():
    _validate_target_count(EXPECTED_INITIAL_TARGETS)
    _validate_target_count(0)

    with pytest.raises(RuntimeError, match="partial/drifted"):
        _validate_target_count(EXPECTED_INITIAL_TARGETS - 1)
