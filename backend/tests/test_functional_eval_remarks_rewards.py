"""기능인제 비고·제재 표기·고객사 포상 테스트."""

from __future__ import annotations

from app.modules.functional_eval.customer_rewards import CUSTOMER_REWARD_NOTE
from app.modules.functional_eval.sanctions import (
    DEFAULT_SANCTION_VIOLATION_CODE,
    build_sanction_display_label,
    institutional_sanction_label,
    resolve_sanction,
    sanction_outcome_label,
)
from app.modules.functional_eval.eval_catalog import (
    assessment_has_bottom,
    assessment_has_issue,
    build_lowest_grade_scores,
    build_safety_scores_with_bottom_for_violation,
    build_top_grade_scores,
    get_criteria,
    violation_safety_criterion_ids,
    violation_safety_targets_already_bottom,
)


def test_default_violation_is_subcontractor_safety_rule():
    assert DEFAULT_SANCTION_VIOLATION_CODE == "SUBCONTRACTOR_SAFETY_RULE"


def test_institutional_sanction_labels():
    assert institutional_sanction_label("VERBAL_WARNING") == "쓰리아웃"
    assert institutional_sanction_label("SAFETY_TRAINING_2H") == "쓰리아웃"
    assert institutional_sanction_label("SAME_DAY_EXPULSION") == "현장퇴출"
    assert institutional_sanction_label("COMPANY_PERMANENT_EXPULSION") == "영구퇴출"


def test_sanction_outcome_labels():
    assert sanction_outcome_label("VERBAL_WARNING") == "쓰리아웃"
    assert sanction_outcome_label("SAME_DAY_EXPULSION") == "현장퇴출"
    assert sanction_outcome_label("SITE_PERMANENT_BAN") == "채용금지"
    assert sanction_outcome_label("COMPANY_PERMANENT_EXPULSION") == "채용금지"


def test_assessment_has_bottom():
    all_top = build_top_grade_scores("SAFETY")
    assert assessment_has_bottom("SAFETY", all_top) is False
    low_scores = build_lowest_grade_scores("SAFETY")
    assert assessment_has_bottom("SAFETY", low_scores) is True


def test_assessment_has_issue():
    all_top = build_top_grade_scores("SAFETY")
    assert assessment_has_issue("SAFETY", all_top) is False
    low_scores = build_lowest_grade_scores("SAFETY")
    assert assessment_has_issue("SAFETY", low_scores) is True


def test_violation_safety_criterion_mapping():
    assert violation_safety_criterion_ids("INST_TBM") == ["c1"]
    assert set(violation_safety_criterion_ids("INST_HOUSEKEEPING")) == {"c7", "c8"}


def test_build_safety_scores_with_bottom_for_violation():
    top_scores = build_top_grade_scores("SAFETY")
    updated = build_safety_scores_with_bottom_for_violation("INST_TBM", top_scores)
    assert updated["c1"] == "BOTTOM"
    assert updated["c2"] == "TOP"


def test_violation_safety_targets_already_bottom():
    top_scores = build_top_grade_scores("SAFETY")
    assert violation_safety_targets_already_bottom("INST_TBM", top_scores) is False
    bottom_c2 = dict(top_scores)
    bottom_c2["c2"] = "BOTTOM"
    assert violation_safety_targets_already_bottom("INST_QR_ACTIVITY", bottom_c2) is True


def test_sanction_display_label_fractions():
    assert build_sanction_display_label("SUBCONTRACTOR_SAFETY_RULE", 1, "VERBAL_WARNING") == "쓰리아웃 (1/3)"
    assert build_sanction_display_label("SUBCONTRACTOR_SAFETY_RULE", 2, "SAFETY_TRAINING_2H") == "쓰리아웃 (2/3)"
    assert (
        build_sanction_display_label("SUBCONTRACTOR_SAFETY_RULE", 3, "COMPANY_PERMANENT_EXPULSION")
        == "채용금지 (3/3)"
    )
    assert build_sanction_display_label("GEN_BASIC_SAFETY", 1, "WARNING") == "쓰리아웃 (1/2)"
    assert build_sanction_display_label("GEN_BASIC_SAFETY", 2, "SAME_DAY_EXPULSION") == "현장퇴출 (2/2)"
    assert build_sanction_display_label("WORK_BELT", 1, "SAME_DAY_EXPULSION") == "현장퇴출"
    assert build_sanction_display_label("SEVERE_THEFT", 1, "SITE_PERMANENT_BAN") == "채용금지"


def test_subcontractor_safety_rule_three_strike():
    r1, s1 = resolve_sanction("SUBCONTRACTOR_SAFETY_RULE", 0)
    r2, s2 = resolve_sanction("SUBCONTRACTOR_SAFETY_RULE", 1)
    r3, s3 = resolve_sanction("SUBCONTRACTOR_SAFETY_RULE", 2)
    assert r1 == "VERBAL_WARNING" and s1 == 1
    assert r2 == "SAFETY_TRAINING_2H" and s2 == 2
    assert r3 == "COMPANY_PERMANENT_EXPULSION" and s3 == 3
    assert institutional_sanction_label(r1) == "쓰리아웃"
    assert institutional_sanction_label(r3) == "영구퇴출"


def test_customer_reward_note_constant():
    assert CUSTOMER_REWARD_NOTE == "고객사포상"
