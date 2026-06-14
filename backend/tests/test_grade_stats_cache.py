from __future__ import annotations

from datetime import date

from app.modules.functional_eval.grade_stats_cache import (
    _allocate_grade_counts,
    _synthetic_grade_distribution,
    is_demo_grade_stats,
)
from app.modules.functional_eval.models import FunctionalEvalPeriod


def test_allocate_grade_counts_sums_to_total():
    counts = _allocate_grade_counts(1211, {"S": 70.0, "A": 15.0, "B": 10.0, "C": 5.0})
    assert sum(counts.values()) == 1211
    assert counts["S"] == 848
    assert counts["A"] == 182
    assert counts["B"] == 121
    assert counts["C"] == 60


def test_synthetic_grade_distribution_all_complete():
    block = _synthetic_grade_distribution(100, attendance_workers=80)
    assert block["workers_total"] == 100
    assert block["graded_total"] == 100
    assert block["ungraded_count"] == 0
    assert block["is_demo"] is True
    assert sum(g["count"] for g in block["grades"].values()) == 100


def test_is_demo_grade_stats_before_live_from():
    period = FunctionalEvalPeriod(
        title="t",
        deadline_date=date(2026, 12, 31),
        is_active=True,
        grade_stats_live_from=date(2026, 6, 16),
    )
    assert is_demo_grade_stats(period, today=date(2026, 6, 15)) is True
    assert is_demo_grade_stats(period, today=date(2026, 6, 16)) is False
