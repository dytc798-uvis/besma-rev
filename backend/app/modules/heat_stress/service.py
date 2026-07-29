from __future__ import annotations

import json
import math

FORMULA_VERSION = "KMA_SUMMER_2022_06_02"

ACTION_LABELS = {
    "WATER": "물 제공 및 섭취",
    "SHADE_COOLING": "그늘·냉방장소 제공",
    "VENTILATION": "통풍·환기",
    "REST": "휴식 실시",
    "WORK_TIME_ADJUSTMENT": "작업시간 조정",
    "COOLING_GEAR": "개인 냉방장구 지급",
    "WORK_STOP": "옥외작업 중지",
    "HEALTH_MONITORING": "건강상태 확인",
    "NOT_IMPLEMENTED": "필요조치 미실시",
    "OTHER": "기타",
}


def calculate_apparent_temperature(air_temperature_c: float, relative_humidity_pct: float) -> float:
    """KMA summer apparent-temperature formula effective 2022-06-02."""
    ta = float(air_temperature_c)
    rh = float(relative_humidity_pct)
    tw = (
        ta * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(ta + rh)
        - math.atan(rh - 1.67633)
        + 0.00391838 * math.pow(rh, 1.5) * math.atan(0.023101 * rh)
        - 4.686035
    )
    value = -0.2442 + 0.55399 * tw + 0.45535 * ta - 0.0022 * tw * tw + 0.00278 * tw * ta + 3.0
    return round(value, 1)


def policy_for(apparent_temperature_c: float) -> dict[str, str]:
    value = float(apparent_temperature_c)
    if value >= 38:
        return {
            "risk_level": "DANGER",
            "risk_label": "극심한 폭염",
            "legal_guidance": "체감온도 33℃ 이상 법정조치: 매 2시간 이내 20분 이상 휴식이 필요합니다.",
            "company_guidance": "38℃ 이상은 재난 수준입니다. 긴급작업 외 옥외작업 중지, 119 대응체계 및 근로자 건강상태를 즉시 확인하세요.",
        }
    if value >= 35:
        return {
            "risk_level": "WARNING",
            "risk_label": "경고",
            "legal_guidance": "체감온도 33℃ 이상 법정조치: 매 2시간 이내 20분 이상 휴식이 필요합니다.",
            "company_guidance": "고강도 작업과 14~17시 옥외작업을 조정·중지하고, 휴식·냉방장구·건강상태 확인을 강화하세요.",
        }
    if value >= 33:
        return {
            "risk_level": "CAUTION",
            "risk_label": "주의",
            "legal_guidance": "체감온도 33℃ 이상 법정조치: 매 2시간 이내 20분 이상 휴식이 필요합니다.",
            "company_guidance": "물·그늘·휴식 제공과 취약근로자 건강상태를 확인하세요. 실제 실시한 조치를 선택해야 합니다.",
        }
    if value >= 31:
        return {
            "risk_level": "INTEREST",
            "risk_label": "관심",
            "legal_guidance": "폭염작업에 해당할 수 있습니다. 체감온도와 실제 조치사항을 작업일자별로 기록하세요.",
            "company_guidance": "물·그늘·환기·휴식·작업시간 조정 중 실제 실시한 조치를 확인하세요.",
        }
    return {
        "risk_level": "NORMAL",
        "risk_label": "일반",
        "legal_guidance": "체감온도를 확인하고 기본 예방조치를 유지하세요.",
        "company_guidance": "물 제공, 환기 및 근로자 건강상태를 확인하세요.",
    }


def action_compliance(apparent_temperature_c: float, actions: list[str]) -> str:
    selected = set(actions)
    if "NOT_IMPLEMENTED" in selected:
        return "ACTION_REQUIRED"
    if apparent_temperature_c >= 33 and not ({"REST", "COOLING_GEAR", "WORK_STOP"} & selected):
        return "ACTION_REQUIRED"
    if apparent_temperature_c >= 31 and not selected:
        return "ACTION_REQUIRED"
    return "RECORDED"


def actions_json(actions: list[str]) -> str:
    return json.dumps(actions, ensure_ascii=False)


def parse_actions(raw: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []
