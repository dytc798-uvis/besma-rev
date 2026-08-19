from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).with_name("public_cases.json")
REQUIRED_POLICY = {
    "survey_status": "제출완료",
    "risk_promotion_status": "승격대상",
    "distribution_status": "전파대상",
    "publication_status": "PUBLISHED",
}
PUBLIC_CASE_FIELDS = (
    "id",
    "category",
    "accident_period",
    "contractor",
    "site",
    "accident_type",
    "injury",
    "incident_summary",
    "work",
    "prevention",
    "survey_status",
    "risk_promotion_status",
    "distribution_status",
)
FORBIDDEN_SOURCE_KEYS = {
    "name",
    "injured_name",
    "manager_name",
    "birth_date",
    "birth_text",
    "age",
    "gender",
    "phone",
    "email",
    "hospital_cost",
    "medicine_cost",
    "medical_document",
    "source_path",
    "internal_path",
    "evidence_path",
    "검증근거",
    "성명",
    "생년월일",
    "연락처",
}
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\b\d{6}-?[1-4]\d{6}\b"),
    re.compile(r"\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b"),
    re.compile(r"\b[A-Za-z]:\\"),
    re.compile(r"[/\\](?:Users|SecureKeys|srv|home)[/\\]", re.IGNORECASE),
)


def _validate_source_record(record: dict[str, Any]) -> None:
    forbidden = FORBIDDEN_SOURCE_KEYS.intersection(record)
    if forbidden:
        raise ValueError(f"공개 사고사례에 금지 필드가 있습니다: {sorted(forbidden)}")
    missing = [key for key in (*PUBLIC_CASE_FIELDS, "publication_status") if key not in record]
    if missing:
        raise ValueError(f"공개 사고사례 필수 필드가 없습니다: {missing}")
    for key, value in record.items():
        if not isinstance(value, str):
            raise ValueError(f"공개 사고사례 필드는 문자열이어야 합니다: {key}")
        if any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
            raise ValueError(f"공개 사고사례에 식별정보 또는 내부 경로 패턴이 있습니다: {key}")


def build_public_dataset(source: dict[str, Any]) -> dict[str, Any]:
    policy = source.get("policy")
    if policy != REQUIRED_POLICY:
        raise ValueError("공개 데이터셋 정책이 산재표 제출·승격·전파·공개승인 기준과 다릅니다.")
    source_cases = source.get("cases")
    if not isinstance(source_cases, list):
        raise ValueError("공개 사고사례 목록 형식이 올바르지 않습니다.")

    public_cases: list[dict[str, str]] = []
    for record in source_cases:
        if not isinstance(record, dict):
            raise ValueError("공개 사고사례 항목 형식이 올바르지 않습니다.")
        _validate_source_record(record)
        if any(record.get(key) != value for key, value in REQUIRED_POLICY.items()):
            continue
        public_cases.append({key: record[key].strip() for key in PUBLIC_CASE_FIELDS})

    return {
        "dataset_id": str(source.get("dataset_id", "")).strip(),
        "title": str(source.get("title", "")).strip(),
        "effective_date": str(source.get("effective_date", "")).strip(),
        "distribution_rule": {
            "survey_status": REQUIRED_POLICY["survey_status"],
            "risk_promotion_status": REQUIRED_POLICY["risk_promotion_status"],
            "distribution_status": REQUIRED_POLICY["distribution_status"],
            "publication_approval": "승인완료",
        },
        "case_count": len(public_cases),
        "cases": public_cases,
    }


@lru_cache(maxsize=1)
def load_public_dataset() -> dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as stream:
        source = json.load(stream)
    return build_public_dataset(source)


def _case_card(case: dict[str, str]) -> str:
    esc = {key: html.escape(value, quote=True) for key, value in case.items()}
    return f"""
      <article class="case-card">
        <div class="case-head">
          <span class="category">{esc['category']}</span>
          <span class="period">{esc['accident_period']}</span>
        </div>
        <h2>{esc['accident_type']} · {esc['work']}</h2>
        <p class="site">{esc['contractor']} · {esc['site']}</p>
        <dl>
          <div><dt>상해</dt><dd>{esc['injury']}</dd></div>
          <div><dt>사고 개요</dt><dd>{esc['incident_summary']}</dd></div>
          <div><dt>재발방지</dt><dd>{esc['prevention']}</dd></div>
        </dl>
        <div class="status-row">
          <span>{esc['survey_status']}</span>
          <span>{esc['risk_promotion_status']}</span>
          <span>{esc['distribution_status']}</span>
        </div>
      </article>
    """


def render_public_page(dataset: dict[str, Any]) -> str:
    cards = "".join(_case_card(case) for case in dataset["cases"])
    effective_date = html.escape(dataset["effective_date"], quote=True)
    case_count = int(dataset["case_count"])
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive,nosnippet">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="ko_KR">
  <meta property="og:title" content="BESMA 전사 공유용 사고사례">
  <meta property="og:description" content="산재표 제출완료 및 공개승인된 비식별 사고사례">
  <meta property="og:url" content="https://api.besma.co.kr/public/accident-cases">
  <title>BESMA 전사 공유용 사고사례</title>
  <style>
    :root {{ color-scheme: light; --navy:#17365d; --blue:#2f75b5; --pale:#eef5fb; --line:#d7e0e8; --ink:#17212b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#f4f7fa; color:var(--ink); font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif; line-height:1.6; }}
    header {{ background:linear-gradient(135deg,var(--navy),#245b8d); color:white; padding:42px 20px 34px; }}
    header .inner, main, footer {{ width:min(1080px,calc(100% - 32px)); margin:auto; }}
    .eyebrow {{ margin:0 0 8px; font-size:.82rem; letter-spacing:.09em; opacity:.8; }}
    h1 {{ margin:0; font-size:clamp(1.65rem,4vw,2.6rem); line-height:1.25; }}
    header p {{ max-width:760px; margin:14px 0 0; color:#e3edf7; }}
    .policy {{ margin:24px 0; padding:18px 20px; background:#fff8df; border:1px solid #ecd993; border-radius:12px; }}
    .policy strong {{ color:#7a5500; }}
    .summary {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }}
    .summary span, .status-row span {{ padding:4px 10px; border-radius:999px; background:#e7f1f9; color:#24557d; font-size:.82rem; font-weight:700; }}
    .case-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; padding-bottom:34px; }}
    .case-card {{ background:white; border:1px solid var(--line); border-radius:14px; padding:20px; box-shadow:0 6px 18px rgba(23,54,93,.06); break-inside:avoid; }}
    .case-head {{ display:flex; justify-content:space-between; gap:12px; color:#52616f; font-size:.86rem; }}
    .category {{ color:var(--blue); font-weight:800; }}
    .case-card h2 {{ margin:9px 0 3px; font-size:1.18rem; }}
    .site {{ margin:0 0 14px; color:#5a6672; font-size:.9rem; }}
    dl, dd {{ margin:0; }}
    dl div {{ border-top:1px solid #edf0f2; padding:10px 0; }}
    dt {{ font-size:.78rem; font-weight:800; color:#52616f; }}
    dd {{ margin-top:3px; }}
    .status-row {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:12px; }}
    .status-row span {{ background:#e9f5ec; color:#27643a; }}
    footer {{ padding:0 0 36px; color:#66727d; font-size:.82rem; }}
    @media (max-width:720px) {{ .case-grid {{ grid-template-columns:1fr; }} header {{ padding-top:30px; }} }}
    @media print {{ body {{ background:white; }} header {{ print-color-adjust:exact; }} .case-card {{ box-shadow:none; }} .case-grid {{ display:block; }} .case-card {{ margin-bottom:14px; }} }}
  </style>
</head>
<body>
  <header><div class="inner">
    <p class="eyebrow">BESMA · SAFETY CASE DISTRIBUTION</p>
    <h1>전사 공유용 사고사례</h1>
    <p>사고관리대장 중 배포기준을 충족하고 별도 공개승인을 받은 사례만 비식별 형태로 제공합니다.</p>
  </div></header>
  <main>
    <section class="policy" aria-label="배포 기준">
      <strong>배포 기준</strong> · 산재표 제출완료 → 위험성평가DB 승격대상 → 사고사례 전파대상 → 공개승인
      <div class="summary"><span>기준일 {effective_date}</span><span>공개 {case_count}건</span><span>인명·정확한 타사 현장·내부자료 제거</span></div>
    </section>
    <section class="case-grid" aria-label="공개 사고사례">{cards}</section>
  </main>
  <footer>이 페이지는 선별된 교육·전파용 사례집이며 전체 사고통계나 사고관리대장을 대체하지 않습니다.</footer>
</body>
</html>"""
