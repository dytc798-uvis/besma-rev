from __future__ import annotations

import json

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
    assert payload["case_count"] == 5
    assert sum(case["category"] == "롯데건설" for case in payload["cases"]) == 3
    assert sum(case["category"] == "타 현장 비식별" for case in payload["cases"]) == 2
    assert all(set(case) == set(PUBLIC_CASE_FIELDS) for case in payload["cases"])
    assert all(case["survey_status"] == "제출완료" for case in payload["cases"])
    assert all(case["risk_promotion_status"] == "승격대상" for case in payload["cases"])
    assert all(case["distribution_status"] == "전파대상" for case in payload["cases"])
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in ("정지훈", "재해자명", "생년월일", "연락처", "검증근거", "source_path", "D:\\\\", "E:\\\\"):
        assert forbidden not in serialized


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


def test_public_page_has_preview_metadata_and_restrictive_headers():
    client = _client()
    response = client.get("/public/accident-cases")
    assert response.status_code == 200
    assert "BESMA 전사 공유용 사고사례" in response.text
    assert 'property="og:title"' in response.text
    assert "산재표 제출완료" in response.text
    assert "미제출(참고)" not in response.text
    assert "정지훈" not in response.text
    assert response.headers["x-robots-tag"].startswith("noindex")
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
