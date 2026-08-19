from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.modules.users import models as user_models  # noqa: E402,F401
from app.modules.sites import models as site_models  # noqa: E402,F401
from app.modules.risk_library.models import (  # noqa: E402
    RiskLibraryContractor,
    RiskLibraryItem,
    RiskLibraryItemContractor,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
)
CONFIRM_TOKEN = "IMPORT-RISK-REV07"
STOPWORDS = {"작업", "위험", "요인", "대책", "전기공사", "개선", "사고사례"}


@dataclass(frozen=True)
class ManifestRow:
    item_id: str
    is_common: bool
    contractors: tuple[str, ...]
    trade: str
    detail_work: str
    work_step: str
    hazard: str
    accident_type: str
    measure: str
    risk_f: int
    risk_s: int
    risk_r: int
    note: str | None
    source_file: str


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def normalized_pair(hazard: str, measure: str) -> tuple[str, str]:
    return clean(hazard).lower(), clean(measure).lower()


def normalize_contractor_key(value: str) -> str:
    text = clean(value).lower()
    for token in ("주식회사", "(주)", "㈜"):
        text = text.replace(token, "")
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def to_int(value: object, default: int) -> int:
    try:
        return int(float(clean(value)))
    except (TypeError, ValueError):
        return default


def parse_manifest(path: Path) -> list[ManifestRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        raw_rows = list(csv.DictReader(stream))
    rows: list[ManifestRow] = []
    seen: set[tuple[str, str]] = set()
    for number, raw in enumerate(raw_rows, start=2):
        hazard = clean(raw.get("hazard"))
        measure = clean(raw.get("measure"))
        trade = clean(raw.get("trade"))
        detail = clean(raw.get("detail_work"))
        if not hazard or not measure or not trade or not detail:
            raise ValueError(f"manifest row {number}: required practical field is empty")
        key = normalized_pair(hazard, measure)
        if key in seen:
            continue
        seen.add(key)
        risk_f = max(1, min(4, to_int(raw.get("btms_frequency"), 1)))
        risk_s = max(1, min(5, to_int(raw.get("btms_severity"), 1)))
        rows.append(
            ManifestRow(
                item_id=clean(raw.get("item_id")),
                is_common=clean(raw.get("is_common")).upper() == "Y",
                contractors=tuple(
                    contractor.strip()
                    for contractor in clean(raw.get("contractors")).split(";")
                    if contractor.strip()
                ),
                trade=trade,
                detail_work=detail,
                work_step=clean(raw.get("work_step")) or detail,
                hazard=hazard,
                accident_type=clean(raw.get("accident_type")),
                measure=measure,
                risk_f=risk_f,
                risk_s=risk_s,
                risk_r=risk_f * risk_s,
                note=clean(raw.get("note")) or None,
                source_file=clean(raw.get("source_file")) or path.name,
            )
        )
    return rows


def keywords_for(row: ManifestRow) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    text = f"{row.trade} {row.detail_work} {row.work_step} {row.hazard} {row.accident_type} {row.measure}"
    for token in re.split(r"[\s,./()\-:;|·]+", text.lower()):
        token = token.strip()
        if len(token) < 2 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token[:100])
    return tokens[:40]


def contractor_profiles(db, rows: list[ManifestRow]) -> dict[str, RiskLibraryContractor]:
    names = sorted({name for row in rows for name in row.contractors})
    existing = {
        row.contractor_key: row
        for row in db.query(RiskLibraryContractor).all()
    }
    result: dict[str, RiskLibraryContractor] = {}
    for name in names:
        key = normalize_contractor_key(name)
        profile = existing.get(key)
        if profile is None:
            profile = RiskLibraryContractor(
                contractor_key=key,
                contractor_name=name,
                evaluation_method="회사 4×5",
                is_active=True,
            )
            db.add(profile)
            db.flush()
            existing[key] = profile
        result[name] = profile
    return result


def import_rows(db, rows: list[ManifestRow], *, apply_changes: bool) -> dict[str, int]:
    current = (
        db.query(RiskLibraryItemRevision, RiskLibraryItem)
        .join(RiskLibraryItem, RiskLibraryItem.id == RiskLibraryItemRevision.item_id)
        .filter(
            RiskLibraryItemRevision.is_current.is_(True),
            RiskLibraryItem.is_active.is_(True),
        )
        .all()
    )
    by_pair = {
        normalized_pair(revision.risk_factor, revision.countermeasure): (revision, item)
        for revision, item in current
    }
    profiles = contractor_profiles(db, rows)
    existing_links = {
        (row.risk_item_id, row.contractor_id)
        for row in db.query(RiskLibraryItemContractor).all()
    }
    counts = {
        "manifest_rows": len(rows),
        "matched_existing": 0,
        "new_items": 0,
        "new_contractor_links": 0,
        "promoted_common": 0,
        "new_keywords": 0,
    }

    for row in rows:
        pair = normalized_pair(row.hazard, row.measure)
        matched = by_pair.get(pair)
        if matched:
            revision, item = matched
            counts["matched_existing"] += 1
            if row.is_common and not item.is_common:
                item.is_common = True
                counts["promoted_common"] += 1
        else:
            item = RiskLibraryItem(
                source_scope="HQ_STANDARD",
                owner_site_id=None,
                is_common=row.is_common,
                is_active=True,
            )
            db.add(item)
            db.flush()
            revision = RiskLibraryItemRevision(
                item_id=item.id,
                revision_no=1,
                is_current=True,
                effective_from=date(2026, 8, 19),
                unit_work=row.trade,
                work_category=row.detail_work,
                trade_type=row.trade,
                process=row.work_step,
                risk_factor=row.hazard,
                risk_cause=row.hazard,
                countermeasure=row.measure,
                note=row.note,
                source_file=row.source_file,
                source_sheet="rev07 웹 반영목록",
                source_page_or_section=row.item_id,
                risk_f=row.risk_f,
                risk_s=row.risk_s,
                risk_r=row.risk_r,
                revision_note="위험성평가 표준모델 rev07",
            )
            db.add(revision)
            db.flush()
            for keyword in keywords_for(row):
                db.add(
                    RiskLibraryKeyword(
                        risk_revision_id=revision.id,
                        keyword=keyword,
                        weight=1.0,
                    )
                )
                counts["new_keywords"] += 1
            by_pair[pair] = (revision, item)
            counts["new_items"] += 1

        for contractor_name in row.contractors:
            profile = profiles[contractor_name]
            link_key = (item.id, profile.id)
            if link_key in existing_links:
                continue
            db.add(
                RiskLibraryItemContractor(
                    risk_item_id=item.id,
                    contractor_id=profile.id,
                )
            )
            existing_links.add(link_key)
            counts["new_contractor_links"] += 1

    if apply_changes:
        db.commit()
    else:
        db.rollback()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Non-destructive rev07 risk-library import (dry-run by default)."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=BACKEND_ROOT / "app" / "seed" / "risk_library_rev07_web.csv",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        parser.error(f"--apply requires --confirm {CONFIRM_TOKEN}")

    rows = parse_manifest(args.manifest.resolve())
    db = SessionLocal()
    try:
        counts = import_rows(db, rows, apply_changes=args.apply)
    finally:
        db.close()
    print("mode=apply" if args.apply else "mode=dry-run")
    for key, value in counts.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
