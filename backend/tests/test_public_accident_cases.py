from __future__ import annotations

import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.public_accident_cases.routes import router
from app.modules.public_accident_cases.service import (
    PUBLIC_CASE_FIELDS,
    REQUIRED_POLICY,
    build_public_dataset,
    load_public_dataset,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_public_dataset_exposes_only_approved_survey_submitted_cases():
    load_public_dataset.cache_clear()
    client = _client()
    response = client.get("/public/accident-cases/data")
    assert response.status_code == 200
    payload = response.json()
    assert payload["case_count"] == 4
    assert sum(case["category"] == "롯데건설" for case in payload["cases"]) == 2
    assert sum(case["category"] == "타 현장 비식별" for case in payload["cases"]) == 2
    assert {case["id"] for case in payload["cases"]} == {
        "LOTTE-2025-09-A",
        "LOTTE-2025-10-A",
        "MASKED-2025-12-A",
        "MASKED-2024-11-A",
    }
    assert {case["accident_period"] for case in payload["cases"]} == {
        "2025-09",
        "2025-10",
        "2025-12",
        "2024-11",
    }
    assert all(set(case) == set(PUBLIC_CASE_FIELDS) for case in payload["cases"])
    assert all(case["survey_status"] == "제출완료" for case in payload["cases"])
    assert all(case["risk_promotion_status"] == "승격대상" for case in payload["cases"])
    assert all(case["distribution_status"] == "전파대상" for case in payload["cases"])
    assert all(
        case["contractor"] == "타사(마스킹)" and case["site"].startswith("타사 현장 ")
        for case in payload["cases"]
        if case["category"] == "타 현장 비식별"
    )
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in (
        "재해자명",
        "생년월일",
        "연락처",
        "검증근거",
        "source_path",
        "D:\\\\",
        "E:\\\\",
        "!R",
        "구리 인창",
        "스팀파이프",
    ):
        assert forbidden not in serialized
    serialized_cases = json.dumps(payload["cases"], ensure_ascii=False)
    assert re.search(r"\b20\d{2}-\d{2}-\d{2}\b", serialized_cases) is None


def test_non_eligible_case_is_filtered_even_when_present_in_source():
    eligible = {key: "표시값" for key in PUBLIC_CASE_FIELDS}
    eligible.update(REQUIRED_POLICY)
    eligible.update({"id": "A", "survey_status": "제출완료", "risk_promotion_status": "승격대상", "distribution_status": "전파대상"})
    ineligible = dict(eligible, id="B", survey_status="미제출")
    source = {
        "dataset_id": "test",
        "title": "test",
        "effective_date": "2026-08-19",
        "policy": dict(REQUIRED_POLICY),
        "cases": [eligible, ineligible],
    }
    result = build_public_dataset(source)
    assert result["case_count"] == 1
    assert result["cases"][0]["id"] == "A"
    assert "publication_status" not in result["cases"][0]


def test_internal_excel_row_reference_is_rejected():
    record = {key: "표시값" for key in PUBLIC_CASE_FIELDS}
    record.update(REQUIRED_POLICY)
    record.update(
        {
            "id": "A",
            "incident_summary": "2025!R13",
            "survey_status": "제출완료",
            "risk_promotion_status": "승격대상",
            "distribution_status": "전파대상",
        }
    )
    source = {
        "dataset_id": "test",
        "title": "test",
        "effective_date": "2026-08-19",
        "policy": dict(REQUIRED_POLICY),
        "cases": [record],
    }
    with pytest.raises(ValueError, match="식별정보 또는 내부 경로"):
        build_public_dataset(source)


def test_public_page_has_preview_metadata_and_restrictive_headers():
    client = _client()
    response = client.get("/public/accident-cases")
    assert response.status_code == 200
    assert "BESMA 전사 공유용 사고사례" in response.text
    assert 'property="og:title"' in response.text
    assert "산재표 제출완료" in response.text
    assert "미제출(참고)" not in response.text
    assert "!R" not in response.text
    assert response.headers["x-robots-tag"].startswith("noindex")
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
