"""출역일보 D열(대표/팀장) 이름 판별."""

from __future__ import annotations

import re

NON_PERSON_REP_LABELS = frozenset(
    {
        "직영",
        "외주",
        "합계",
        "소계",
        "미배정",
        "없음",
        "공무",
        "소장",
        "팀장",
        "대표",
        "미지정",
        "해당없음",
        "없",
    }
)


def is_person_rep_name(name: str) -> bool:
    """한글 인명 2~4자만 팀장으로 인정 (업체명·영문 혼합 제외)."""
    text = (name or "").strip().replace(" ", "")
    if not text or text in NON_PERSON_REP_LABELS:
        return False
    if re.search(r"[A-Za-z0-9]", text):
        return False
    if not re.fullmatch(r"[가-힣]{2,4}", text):
        return False
    return True


def resolve_team_rep_name(rep_raw: str | None, manager_name: str) -> str:
    """D열 팀장명 → 평가 그룹 키. 비인명이면 소장 직영으로 합친다."""
    manager = (manager_name or "").strip()
    rep = (rep_raw or "").strip()
    if not rep or rep == manager:
        return manager
    if not is_person_rep_name(rep):
        return manager
    return rep
