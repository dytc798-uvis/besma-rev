from __future__ import annotations

from app.modules.functional_eval.eval_catalog import compute_assessment, get_criteria, normalize_grade_code
from app.modules.functional_eval.import_diff import attendance_entry_fields, worker_needs_attendance_update
from app.modules.functional_eval.models import FunctionalEvalWorker


def test_normalize_grade_code_maps_d_to_c():
    assert normalize_grade_code("D") == "C"
    assert normalize_grade_code("S") == "S"


def test_score_to_grade_matches_excel_no_d():
    criteria = get_criteria("FUNCTIONAL")
    # 모든 항목 최하(BOTTOM) — 엑셀 기준 C, D 없음
    scores = {c["id"]: c["grades"][-1]["key"] for c in criteria}
    result = compute_assessment("FUNCTIONAL", scores)
    assert result["grade_code"] in {"S", "A", "B", "C"}
    assert result["grade_code"] != "D"


def test_worker_needs_attendance_update_on_reactivation():
    worker = FunctionalEvalWorker(
        period_id=1,
        site_code="24025",
        row_no=1,
        name="홍길동",
        rrn_hash="h1",
        is_active=False,
        removed_at=None,
    )

    class Row:
        name = "홍길동"
        job_name = "철근"
        rrn_masked = "900101-*******"

    assert worker_needs_attendance_update(
        worker, Row(), site_code="24025", site_name="C18", is_manager=False
    )


def test_attendance_entry_fields_normalized():
    assert attendance_entry_fields(
        site_code="24025",
        name=" 홍길동 ",
        job_name="철근",
        rep_name=None,
        erp_site_label="현장명: C18",
    ) == ("24025", "홍길동", "철근", "", "현장명: C18")
