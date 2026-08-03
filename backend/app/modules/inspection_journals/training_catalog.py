from __future__ import annotations


REGULAR_CONTENT = """1. 근로자 안전보건교육(제26조제1항 관련)
○ 산업안전 및 사고 예방에 관한 사항
○ 산업보건 및 직업병 예방에 관한 사항
○ 위험성 평가에 관한 사항
○ 건강증진 및 질병 예방에 관한 사항
○ 유해ㆍ위험 작업환경 관리에 관한 사항
○ 산업안전보건법령 및 산업재해보상보험 제도에 관한 사항
○ 직무스트레스 예방 및 관리에 관한 사항
○ 직장 내 괴롭힘, 고객의 폭언 등으로 인한 건강장해 예방 및 관리에 관한 사항"""

COMMON_WORK_CONTENT = """1. 근로자 안전보건교육(제26조제1항 관련)
○ 산업안전 및 사고 예방에 관한 사항
○ 산업보건 및 직업병 예방에 관한 사항
○ 위험성 평가에 관한 사항
○ 산업안전보건법령 및 산업재해보상보험 제도에 관한 사항
○ 직무스트레스 예방 및 관리에 관한 사항
○ 직장 내 괴롭힘, 고객의 폭언 등으로 인한 건강장해 예방 및 관리에 관한 사항
○ 기계ㆍ기구의 위험성과 작업의 순서 및 동선에 관한 사항
○ 작업 개시 전 점검에 관한 사항
○ 정리정돈 및 청소에 관한 사항
○ 사고 발생 시 긴급조치에 관한 사항
○ 물질안전보건자료에 관한 사항"""


def _special(title: str, bullets: tuple[str, ...]) -> str:
    lines = [COMMON_WORK_CONTENT, "", f"2. {title}"]
    lines.extend(f"○ {bullet}" for bullet in bullets)
    return "\n".join(lines)


TRAINING_CATALOG = {
    "REGULAR": {
        "label": "정기교육",
        "source_sheet": "정기교육",
        "legal_content": REGULAR_CONTENT,
    },
    "HIRING": {
        "label": "채용 시 교육",
        "source_sheet": "채용작업내용변경시",
        "legal_content": COMMON_WORK_CONTENT,
    },
    "WORK_CHANGE": {
        "label": "작업내용 변경 시 교육",
        "source_sheet": "채용작업내용변경시",
        "legal_content": COMMON_WORK_CONTENT,
    },
    "SPECIAL_ELECTRICAL": {
        "label": "특별교육 · 전기",
        "source_sheet": "특별교육(전기)",
        "legal_content": _special(
            "전압이 75볼트 이상인 정전 및 활선작업",
            (
                "전기의 위험성 및 전격 방지에 관한 사항",
                "해당 설비의 보수 및 점검에 관한 사항",
                "정전작업·활선작업 시의 안전작업방법 및 순서에 관한 사항",
                "절연용 보호구 및 활선작업용 기구 등의 사용에 관한 사항",
                "그 밖에 안전·보건관리에 필요한 사항",
            ),
        ),
    },
    "SPECIAL_MSDS": {
        "label": "특별교육 · MSDS 유해화학물질",
        "source_sheet": "특별교육(MSDS)",
        "legal_content": _special(
            "(MSDS) 유해화학물질 교육 - 물질명은 추가내용에 기재",
            (
                "폭발성·물반응성·자기반응성·자기발열성 물질, 자연발화성 액체·고체 및 인화성 액체의 성질이나 상태에 관한 사항",
                "폭발 한계점, 발화점 및 인화점 등에 관한 사항",
                "취급방법 및 안전수칙에 관한 사항",
                "이상 발견 시의 응급처치 및 대피 요령에 관한 사항",
                "화기·정전기·충격 및 자연발화 등의 위험방지에 관한 사항",
                "작업순서, 취급주의사항 및 방호거리 등에 관한 사항",
                "그 밖에 안전·보건관리에 필요한 사항",
            ),
        ),
    },
    "SPECIAL_CRANE": {
        "label": "특별교육 · 1톤 이상 크레인",
        "source_sheet": "특별교육(크레인)",
        "legal_content": _special(
            "1톤 이상의 크레인을 사용하는 작업",
            (
                "방호장치의 종류, 기능 및 취급에 관한 사항",
                "걸고리·와이어로프 및 비상정지장치 등의 기계·기구 점검에 관한 사항",
                "화물의 취급 및 안전작업방법에 관한 사항",
                "신호방법 및 공동작업에 관한 사항",
                "인양 물건의 위험성 및 낙하·비래(飛來)·충돌재해 예방에 관한 사항",
                "인양물이 적재될 지반의 조건, 인양하중, 풍압 등이 인양물과 타워크레인에 미치는 영향",
                "그 밖에 안전·보건관리에 필요한 사항",
            ),
        ),
    },
    "SPECIAL_AERIAL_LIFT": {
        "label": "특별교육 · 하역기계·고소작업대",
        "source_sheet": "특별교육(하역기계-고소작업대)",
        "legal_content": _special(
            "고소작업대 등 운반·하역기계 작업",
            (
                "운반하역기계 및 부속설비의 점검에 관한 사항",
                "작업순서와 방법에 관한 사항",
                "안전운전방법에 관한 사항",
                "화물의 취급 및 작업신호에 관한 사항",
                "그 밖에 안전·보건관리에 필요한 사항",
            ),
        ),
    },
    "SPECIAL_CONFINED_SPACE": {
        "label": "특별교육 · 밀폐공간·습윤장소 용접",
        "source_sheet": "특별교육(밀폐공간)",
        "legal_content": _special(
            "밀폐된 장소에서 하는 용접작업 또는 습한 장소에서 하는 전기용접 작업",
            (
                "작업순서, 안전작업방법 및 수칙에 관한 사항",
                "환기설비에 관한 사항",
                "전격 방지 및 보호구 착용에 관한 사항",
                "질식 시 응급조치에 관한 사항",
                "작업환경 점검에 관한 사항",
                "그 밖에 안전·보건관리에 필요한 사항",
            ),
        ),
    },
}


def public_catalog() -> list[dict[str, str]]:
    return [
        {"code": code, "label": row["label"], "legal_content": row["legal_content"]}
        for code, row in TRAINING_CATALOG.items()
    ]
