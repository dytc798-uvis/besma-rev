from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster
from app.modules.sites.models import Site
from app.modules.users import models as user_models  # noqa: F401
from app.modules.workers import models as worker_models  # noqa: F401


@dataclass(frozen=True)
class SamsungRequirementInput:
    title: str
    requirement_code: str
    section: str
    period_label: str
    is_required_default: bool = True
    is_enabled: bool = True


@dataclass(frozen=True)
class SamsungRequirementSpec:
    title: str
    requirement_code: str
    section: str
    period: str
    is_required_default: bool
    is_enabled: bool
    document_type_code: str


RAW_REQUIREMENTS: list[SamsungRequirementInput] = [
    SamsungRequirementInput("소통회의 결과보고서", "SAMSUNG_EXTRA_001", "운영 서류", "월1회"),
    SamsungRequirementInput("근로자 의견청취 관리대장", "SAMSUNG_EXTRA_002", "운영 서류", "월1회"),
    SamsungRequirementInput("포상사진", "SAMSUNG_EXTRA_003", "운영 서류", "월1회"),
    SamsungRequirementInput("수시 위험성평가표", "SAMSUNG_EXTRA_004", "운영 서류", "월1회"),
    SamsungRequirementInput("현장 업무분장표", "SAMSUNG_EXTRA_005", "법적 서류", "발생시"),
    SamsungRequirementInput("안전보건관리책임자/안전관리자 선임계 및 증빙", "SAMSUNG_EXTRA_006", "법적 서류", "발생시"),
    SamsungRequirementInput("일일안전회의록 및 위험성평가", "SAMSUNG_EXTRA_007", "운영 서류", "매일"),
    SamsungRequirementInput("TBM 교육 결과보고서", "SAMSUNG_EXTRA_008", "운영 서류", "매일"),
    SamsungRequirementInput("위험성평가 이행 점검표", "SAMSUNG_EXTRA_009", "운영 서류", "매일"),
    SamsungRequirementInput("안전관리자 업무일지", "SAMSUNG_EXTRA_010", "운영 서류", "매일"),
    SamsungRequirementInput("비상대응 훈련 결과보고서", "SAMSUNG_EXTRA_011", "법적 서류", "발생시"),
    SamsungRequirementInput("비상연락망 / 비상조직도", "SAMSUNG_EXTRA_012", "법적 서류", "발생시"),
    SamsungRequirementInput("비상사태 매뉴얼", "SAMSUNG_EXTRA_013", "법적 서류", "발생시"),
    SamsungRequirementInput("부적합사항 조치 결과보고서", "SAMSUNG_EXTRA_014", "운영 서류", "발생시"),
    SamsungRequirementInput("부적합사항 관리대장", "SAMSUNG_EXTRA_015", "운영 서류", "월1회"),
]

PERIOD_MAP = {
    "매일": "DAILY",
    "월1회": "MONTHLY",
    "발생시": "ADHOC",
}


def _period_to_frequency(period_label: str) -> str:
    mapped = PERIOD_MAP.get(period_label.strip())
    if not mapped:
        raise ValueError(f"Unsupported period label: {period_label}")
    return mapped


def _section_to_document_type_code(section: str) -> str:
    normalized = section.strip()
    if normalized == "법적 서류":
        return "LEGAL_DOC"
    if normalized == "운영 서류":
        return "DAILY_DOC"
    raise ValueError(f"Unsupported section: {section}")


def samsung_requirement_specs() -> list[SamsungRequirementSpec]:
    return [
        SamsungRequirementSpec(
            title=item.title,
            requirement_code=item.requirement_code,
            section=item.section,
            period=_period_to_frequency(item.period_label),
            is_required_default=item.is_required_default,
            is_enabled=item.is_enabled,
            document_type_code=_section_to_document_type_code(item.section),
        )
        for item in RAW_REQUIREMENTS
    ]


def current_requirement_titles(db) -> set[str]:
    rows = db.query(DocumentRequirement.title).all()
    return {title.strip() for (title,) in rows if title and title.strip()}


def compute_missing_requirements(existing_titles: set[str]) -> list[SamsungRequirementSpec]:
    missing: list[SamsungRequirementSpec] = []
    for spec in samsung_requirement_specs():
        if spec.title in existing_titles:
            continue
        missing.append(spec)
    return missing


def apply_missing_requirements(db, missing: list[SamsungRequirementSpec]) -> list[dict[str, str]]:
    if not missing:
        return []

    type_by_code = {
        row.code: row
        for row in db.query(DocumentTypeMaster).filter(
            DocumentTypeMaster.code.in_({"LEGAL_DOC", "DAILY_DOC"})
        ).all()
    }
    if "LEGAL_DOC" not in type_by_code or "DAILY_DOC" not in type_by_code:
        raise RuntimeError("DocumentTypeMaster LEGAL_DOC/DAILY_DOC must exist before running this seed.")

    sites = db.query(Site).all()
    if not sites:
        return []

    max_order_by_site: dict[int, int] = {}
    for site in sites:
        max_order = (
            db.query(DocumentRequirement.display_order)
            .filter(DocumentRequirement.site_id == site.id)
            .order_by(DocumentRequirement.display_order.desc())
            .first()
        )
        max_order_by_site[site.id] = int(max_order[0]) if max_order and max_order[0] is not None else 0

    inserted: list[dict[str, str]] = []
    for spec in missing:
        dt = type_by_code[spec.document_type_code]
        for site in sites:
            exists = (
                db.query(DocumentRequirement.id)
                .filter(
                    DocumentRequirement.site_id == site.id,
                    DocumentRequirement.title == spec.title,
                )
                .first()
            )
            if exists:
                continue

            max_order_by_site[site.id] += 1
            db.add(
                DocumentRequirement(
                    site_id=site.id,
                    document_type_id=dt.id,
                    code=spec.requirement_code,
                    title=spec.title,
                    frequency=spec.period,
                    is_required=spec.is_required_default,
                    is_enabled=spec.is_enabled,
                    display_order=max_order_by_site[site.id],
                    due_rule_text=None,
                    note=None,
                )
            )
        inserted.append(
            {
                "title": spec.title,
                "requirement_code": spec.requirement_code,
                "section": spec.section,
                "period": spec.period,
            }
        )

    db.commit()
    return inserted


def run() -> dict[str, object]:
    db = SessionLocal()
    try:
        existing_titles = current_requirement_titles(db)
        missing = compute_missing_requirements(existing_titles)
        added = apply_missing_requirements(db, missing)
        return {
            "missing_count": len(missing),
            "added_count": len(added),
            "added": added,
        }
    finally:
        db.close()


def main() -> None:
    result = run()
    if result["added_count"] == 0:
        print("NO ACTION NEEDED")
        return
    print("ADDED REQUIREMENTS")
    for item in result["added"]:
        print(item)


if __name__ == "__main__":
    main()
