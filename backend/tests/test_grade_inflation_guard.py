"""등급 인플레이션 방지 테스트."""

from __future__ import annotations

import pytest

from app.modules.functional_eval.grade_inflation_guard import (
    compute_grade_inflation_review,
    validate_grade_inflation_reasons,
)


def _worker(functional_grade: str, *, complete: bool = True) -> dict:
    if not complete:
        return {"functional_assessment": {"is_complete": False}, "safety_assessment": {"is_complete": False}}
    return {
        "functional_assessment": {"is_complete": True, "grade_code": functional_grade, "grade_label": f"{functional_grade}등급"},
        "safety_assessment": {"is_complete": True, "grade_code": "S", "grade_label": "S등급"},
    }


def test_ten_workers_two_s_functional_ratio_ok():
    workers = [_worker("S") for _ in range(2)] + [_worker("B") for _ in range(8)]
    review = compute_grade_inflation_review(workers)
    assert review["s_over_limit"] is False
    assert review["no_c_grade"] is False


def test_ten_workers_three_s_functional_requires_reason():
    workers = [_worker("S") for _ in range(3)] + [_worker("B") for _ in range(7)]
    review = compute_grade_inflation_review(workers)
    assert review["s_over_limit"] is True
    with pytest.raises(ValueError, match="S_GRADE"):
        validate_grade_inflation_reasons(review, s_over_limit_reason="짧음")
    validate_grade_inflation_reasons(
        review,
        s_over_limit_reason="숙련공 비중이 높아 기능/품질 S등급 비율이 높습니다.",
    )


def test_all_safety_s_does_not_trigger_functional_limit_when_functional_is_b():
    workers = [_worker("B") for _ in range(10)]
    review = compute_grade_inflation_review(workers)
    assert review["s_over_limit"] is False
    assert review["grade_distribution_snapshot"]["s_count"] == 0


def test_c_zero_does_not_require_reason():
    workers = [_worker("B") for _ in range(10)]
    review = compute_grade_inflation_review(workers)
    assert review["no_c_grade"] is False
    validate_grade_inflation_reasons(review, s_over_limit_reason=None)
