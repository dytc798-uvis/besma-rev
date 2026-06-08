"""기능인제 로그인 ID용 현장 별칭 (예: 대우청라, 금호마곡)."""

from __future__ import annotations

import re

# 현장명 키워드 → 별칭에 붙일 짧은 토큰 (긴 것부터 매칭)
_PROJECT_TOKENS: tuple[tuple[str, str], ...] = (
    ("바이오로직스", "바이오"),
    ("바이오", "바이오"),
    ("청라C18", "청라"),
    ("청라", "청라"),
    ("C18BL", "청라"),
    ("마곡", "마곡"),
    ("고잔", "고잔"),
    ("검단", "검단"),
    ("장위", "장위"),
    ("브레인시티", "브레인"),
    ("효성", "효성"),
    ("원당", "원당"),
    ("평택", "평택"),
    ("고양", "고양"),
    ("양주", "양주"),
    ("제주", "제주"),
    ("노원", "노원"),
    ("대구", "대구"),
    ("스타필드", "스타필드"),
    ("창원", "창원"),
    ("신세계", "신세계"),
    ("PROVIDENCE", "바이오"),
)


def _contractor_short(bracket: str) -> str:
    text = bracket.strip()
    m = re.search(r"([가-힣A-Za-z]{2,6})건설", text)
    if m:
        name = m.group(1)
        return name[:4] if len(name) > 4 else name
    m = re.search(r"신세계", text)
    if m:
        return "신세계"
    m = re.search(r"([가-힣]{2,4})", text)
    return m.group(1) if m else ""


def derive_site_alias(erp_site_name: str) -> str:
    """ERP 현장명 → 로그인 접두 별칭 (예: [1.대우건설] 청라C18… → 대우청라)."""
    text = (erp_site_name or "").strip()
    if text.startswith("현장명:"):
        text = text.replace("현장명:", "", 1).strip()

    contractor = ""
    project = text
    m = re.match(r"\[[^\]]+\]\s*(.*)", text)
    if m:
        bracket = re.match(r"\[([^\]]+)\]", text)
        bracket_inner = bracket.group(1) if bracket else ""
        contractor = _contractor_short(bracket_inner)
        project = m.group(1).strip()

    token = ""
    upper = project.upper()
    for needle, short in _PROJECT_TOKENS:
        if needle.upper() in upper or needle in project:
            token = short
            break

    if not token:
        words = re.findall(r"[가-힣]{2,4}", project)
        if words:
            token = words[0][:4]

    alias = f"{contractor}{token}".strip()
    if not alias:
        alias = re.sub(r"[^\w가-힣]", "", project)[:6] or "현장"
    return alias[:20]


def build_eval_login_id(site_alias: str, person_name: str) -> str:
    alias = (site_alias or "").strip()
    name = (person_name or "").strip().replace(" ", "")
    if not alias or not name:
        return ""
    return f"{alias}-{name}"
