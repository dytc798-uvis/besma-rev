from types import SimpleNamespace

from app.modules.heat_stress.pdf import build_default_pdf
from app.modules.heat_stress.service import (
    FORMULA_VERSION,
    action_compliance,
    calculate_apparent_temperature,
    policy_for,
)


def test_kma_formula_and_legal_thresholds():
    value = calculate_apparent_temperature(33.0, 70.0)
    assert value == 34.3
    assert FORMULA_VERSION == "KMA_SUMMER_2022_06_02"
    assert "매 2시간 이내 20분 이상 휴식" in policy_for(33.0)["legal_guidance"]
    assert policy_for(30.9)["risk_level"] == "NORMAL"
    assert policy_for(31.0)["risk_level"] == "INTEREST"
    assert policy_for(38.0)["risk_level"] == "DANGER"


def test_actual_action_is_never_automatically_completed():
    assert action_compliance(33.0, []) == "ACTION_REQUIRED"
    assert action_compliance(33.0, ["WATER"]) == "ACTION_REQUIRED"
    assert action_compliance(33.0, ["REST"]) == "RECORDED"
    assert action_compliance(30.0, []) == "RECORDED"
    assert action_compliance(30.0, ["NOT_IMPLEMENTED"]) == "ACTION_REQUIRED"


def test_default_pdf_contains_one_valid_page():
    from datetime import datetime

    row = SimpleNamespace(
        id=1,
        measured_at=datetime(2026, 7, 29, 14, 0),
        work_location="옥외 작업장",
        work_process="배관",
        measurement_source="ON_SITE",
        air_temperature_c=33.0,
        relative_humidity_pct=70.0,
        apparent_temperature_c=37.0,
        risk_level="WARNING",
        legal_guidance="매 2시간 이내 20분 이상 휴식",
        company_guidance="옥외작업 조정",
        actual_actions_json='["REST", "WATER"]',
        action_notes="14:00~14:20 휴식",
        action_compliance="RECORDED",
        recorder_name="점검자",
        recorder_signed_at=datetime(2026, 7, 29, 14, 5),
        recorder_signature_data=None,
        confirmer_name=None,
        confirmer_signed_at=None,
        confirmer_signature_data=None,
        template_code="HQ_DEFAULT_V1",
    )
    content = build_default_pdf(row, "테스트 현장")
    assert content.startswith(b"%PDF-")
    assert len(content) > 1000
