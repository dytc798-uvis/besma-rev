"""기능인제 안전관리 이행준수 평가 제재 기준 (DECISION-087, 양식 3-2·제재표)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SanctionRuleType = Literal[
    "IMMEDIATE_SAME_DAY",
    "IMMEDIATE_SITE_PERMANENT",
    "IMMEDIATE_SITE_PERMANENT_BAN",
    "TWO_STRIKE",
    "THREE_STRIKE",
]


@dataclass(frozen=True)
class ViolationItem:
    code: str
    category: str
    category_label: str
    label: str
    sanction_rule: SanctionRuleType
    sort_order: int


VIOLATION_CATALOG: tuple[ViolationItem, ...] = (
    # ── 1. 작업위반: 1회 적발 시 당일 현장 퇴출 ──
    ViolationItem("WORK_BELT", "WORK_VIOLATION", "작업위반", "고소·모서리 작업 시 안전벨트 미체결", "IMMEDIATE_SAME_DAY", 101),
    ViolationItem("WORK_ALCOHOL_VIOLENCE", "WORK_VIOLATION", "작업위반", "음주·폭력행위", "IMMEDIATE_SAME_DAY", 102),
    ViolationItem("WORK_HOT_SPARK", "WORK_VIOLATION", "작업위반", "화기작업 불티·불꽃 방산 미실시", "IMMEDIATE_SAME_DAY", 103),
    ViolationItem("WORK_SAFETY_FACILITY", "WORK_VIOLATION", "작업위반", "안전시설물 무단 해체", "IMMEDIATE_SAME_DAY", 104),
    ViolationItem("WORK_STOP", "WORK_VIOLATION", "작업위반", "공종간 작업중지 유발", "IMMEDIATE_SAME_DAY", 105),
    ViolationItem("WORK_UNAUTHORIZED", "WORK_VIOLATION", "작업위반", "승인 없는 무단 작업", "IMMEDIATE_SAME_DAY", 106),
    # ── 2. 안전사고: 1회 위반 시 현장 영구 퇴출 ──
    ViolationItem("ACCIDENT_LATE_REPORT", "SAFETY_ACCIDENT", "안전사고", "사고 지연 보고(안전·공무·소장)", "IMMEDIATE_SITE_PERMANENT", 201),
    ViolationItem("ACCIDENT_UNREPORTED", "SAFETY_ACCIDENT", "안전사고", "미보고 후 퇴근·병원 단독 방문", "IMMEDIATE_SITE_PERMANENT", 202),
    # ── 3. 안전 지시 불이행(삼진아웃): 1 구두경고 → 2 교육2h → 3 영구퇴출 ──
    ViolationItem("INST_TBM", "SAFETY_INSTRUCTION", "안전 지시 불이행", "TBM 참석·이행 미준수", "THREE_STRIKE", 301),
    ViolationItem("INST_QR_ACTIVITY", "SAFETY_INSTRUCTION", "안전 지시 불이행", "협력사 안전활동(QR) 미이행", "THREE_STRIKE", 302),
    ViolationItem("INST_PPE", "SAFETY_INSTRUCTION", "안전 지시 불이행", "개인보호구 미착용", "THREE_STRIKE", 303),
    ViolationItem("INST_TOOL", "SAFETY_INSTRUCTION", "안전 지시 불이행", "기본 공구·장비 관리 미흡", "THREE_STRIKE", 304),
    ViolationItem("INST_WALKING", "SAFETY_INSTRUCTION", "안전 지시 불이행", "이동·소통 수칙 위반(주머니·휴대폰·이어폰)", "THREE_STRIKE", 305),
    ViolationItem("INST_SMOKING_AREA", "SAFETY_INSTRUCTION", "안전 지시 불이행", "지정 흡연구역 외 흡연", "THREE_STRIKE", 306),
    ViolationItem("INST_HOUSEKEEPING", "SAFETY_INSTRUCTION", "안전 지시 불이행", "작업 후 정리정돈·출결·무재해 기록 미준수", "THREE_STRIKE", 307),
    # ── 3-1. 도급사 안전수칙 (삼진아웃) ──
    ViolationItem(
        "SUBCONTRACTOR_SAFETY_RULE",
        "SUBCONTRACTOR_SAFETY",
        "도급사 안전수칙",
        "도급사 안전수칙 위반",
        "THREE_STRIKE",
        308,
    ),
    # ── 4. 일반 안전수칙(2회제): 1 경고 → 2 퇴출 ──
    ViolationItem("GEN_BASIC_SAFETY", "GENERAL_SAFETY", "일반 안전수칙", "기초 안전수칙 위반", "TWO_STRIKE", 401),
    ViolationItem("GEN_INAPPROPRIATE", "GENERAL_SAFETY", "일반 안전수칙", "부적절한 언행·태도", "TWO_STRIKE", 402),
    ViolationItem("GEN_NEGLIGENCE", "GENERAL_SAFETY", "일반 안전수칙", "작업 태만", "TWO_STRIKE", 403),
    ViolationItem("GEN_PPE", "GENERAL_SAFETY", "일반 안전수칙", "안전모·안전벨트 등 보호구 미착용", "TWO_STRIKE", 404),
    ViolationItem("GEN_SMOKING", "GENERAL_SAFETY", "일반 안전수칙", "작업장 내 흡연", "TWO_STRIKE", 405),
    # ── 5. 즉시 퇴출·영구 출입 금지(1회) ──
    ViolationItem("SEVERE_DRINKING", "SEVERE_VIOLATION", "중대 위반", "음주", "IMMEDIATE_SITE_PERMANENT_BAN", 501),
    ViolationItem("SEVERE_SMOKING", "SEVERE_VIOLATION", "중대 위반", "지정 구역 외 흡연(중대)", "IMMEDIATE_SITE_PERMANENT_BAN", 502),
    ViolationItem("SEVERE_ASSAULT", "SEVERE_VIOLATION", "중대 위반", "폭행·도박", "IMMEDIATE_SITE_PERMANENT_BAN", 503),
    ViolationItem("SEVERE_THEFT", "SEVERE_VIOLATION", "중대 위반", "절도", "IMMEDIATE_SITE_PERMANENT_BAN", 504),
    ViolationItem("SEVERE_UNAUTHORIZED_ENTRY", "SEVERE_VIOLATION", "중대 위반", "통제구역 무단 출입", "IMMEDIATE_SITE_PERMANENT_BAN", 505),
    ViolationItem("SEVERE_INSUBORDINATION", "SEVERE_VIOLATION", "중대 위반", "관리자 지시 불이행·현장 소란", "IMMEDIATE_SITE_PERMANENT_BAN", 506),
)

VIOLATION_BY_CODE = {v.code: v for v in VIOLATION_CATALOG}


SANCTION_RESULT_LABELS: dict[str, str] = {
    "VERBAL_WARNING": "구두 경고",
    "WARNING": "경고",
    "SAFETY_TRAINING_2H": "별도 안전교육 2시간",
    "SAME_DAY_EXPULSION": "당일 현장 퇴출",
    "SITE_PERMANENT_EXPULSION": "현장 영구 퇴출",
    "SITE_PERMANENT_BAN": "즉시 퇴출 및 영구 출입 금지",
    "COMPANY_PERMANENT_EXPULSION": "부현전기 영구 퇴출",
}

# 본 제도 표시용 — 쓰리아웃 / 현장퇴출 / 영구퇴출
INSTITUTIONAL_SANCTION_LABELS: dict[str, str] = {
    "VERBAL_WARNING": "쓰리아웃",
    "WARNING": "쓰리아웃",
    "SAFETY_TRAINING_2H": "쓰리아웃",
    "SAME_DAY_EXPULSION": "현장퇴출",
    "SITE_PERMANENT_EXPULSION": "영구퇴출",
    "SITE_PERMANENT_BAN": "영구퇴출",
    "COMPANY_PERMANENT_EXPULSION": "영구퇴출",
}

DEFAULT_SANCTION_VIOLATION_CODE = "SUBCONTRACTOR_SAFETY_RULE"


def institutional_sanction_label(result: str) -> str:
    return INSTITUTIONAL_SANCTION_LABELS.get(result, SANCTION_RESULT_LABELS.get(result, result))


def strike_max_for_rule(rule: SanctionRuleType) -> int:
    if rule == "THREE_STRIKE":
        return 3
    if rule == "TWO_STRIKE":
        return 2
    return 1


def sanction_outcome_label(result: str) -> str:
    """UI 표시용 — 쓰리아웃 / 현장퇴출 / 채용금지."""
    if is_permanent_sanction(result):
        return "채용금지"
    if result in {"VERBAL_WARNING", "WARNING", "SAFETY_TRAINING_2H"}:
        return "쓰리아웃"
    if result == "SAME_DAY_EXPULSION":
        return "현장퇴출"
    return institutional_sanction_label(result)


def build_sanction_display_label(violation_code: str, strike_number: int, sanction_result: str) -> str:
    """제재 이력·명단 — 쓰리아웃 (1/3), 현장퇴출, 채용금지 (3/3) 등."""
    item = VIOLATION_BY_CODE.get(violation_code)
    max_strikes = strike_max_for_rule(item.sanction_rule) if item else 1
    outcome = sanction_outcome_label(sanction_result)
    if max_strikes <= 1:
        return outcome
    return f"{outcome} ({strike_number}/{max_strikes})"


def resolve_sanction(violation_code: str, prior_strike_count: int) -> tuple[str, int]:
    """
    위반 코드와 동일 규칙군 누적 횟수로 제재 결과·이번 strike 차수를 반환한다.
    prior_strike_count: 이번 기록 전 동일 violation_code 건수
    """
    item = VIOLATION_BY_CODE.get(violation_code)
    if item is None:
        raise ValueError(f"Unknown violation code: {violation_code}")

    strike = prior_strike_count + 1

    if item.sanction_rule == "IMMEDIATE_SAME_DAY":
        return "SAME_DAY_EXPULSION", strike
    if item.sanction_rule == "IMMEDIATE_SITE_PERMANENT":
        return "SITE_PERMANENT_EXPULSION", strike
    if item.sanction_rule == "IMMEDIATE_SITE_PERMANENT_BAN":
        return "SITE_PERMANENT_BAN", strike
    if item.sanction_rule == "TWO_STRIKE":
        if strike >= 2:
            return "SAME_DAY_EXPULSION", strike
        return "WARNING", strike
    if item.sanction_rule == "THREE_STRIKE":
        if strike >= 3:
            return "COMPANY_PERMANENT_EXPULSION", strike
        if strike == 2:
            return "SAFETY_TRAINING_2H", strike
        return "VERBAL_WARNING", strike

    raise ValueError(f"Unhandled sanction rule: {item.sanction_rule}")


PERMANENT_SANCTION_RESULTS: frozenset[str] = frozenset(
    {
        "COMPANY_PERMANENT_EXPULSION",
        "SITE_PERMANENT_BAN",
        "SITE_PERMANENT_EXPULSION",
    }
)


def is_permanent_sanction(result: str) -> bool:
    return result in PERMANENT_SANCTION_RESULTS


def worker_status_from_sanctions(sanction_results: list[str]) -> str:
    """최종 근로자 제재 상태(표시용)."""
    priority = [
        "COMPANY_PERMANENT_EXPULSION",
        "SITE_PERMANENT_BAN",
        "SITE_PERMANENT_EXPULSION",
        "SAME_DAY_EXPULSION",
        "SAFETY_TRAINING_2H",
        "WARNING",
        "VERBAL_WARNING",
    ]
    if not sanction_results:
        return "NONE"
    for code in priority:
        if code in sanction_results:
            return code
    return "NONE"
