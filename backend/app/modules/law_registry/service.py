from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.law_registry.models import LawArticleItem, LawMaster, LawRevisionHistory


DEFAULT_LIMIT = 10

LAW_TYPE_ALIASES = {
    "act": "법",
    "법": "법",
    "enforcement_decree": "령",
    "시행령": "령",
    "령": "령",
    "enforcement_rule": "규칙",
    "rule": "규칙",
    "규칙": "규칙",
    "guideline": "고시",
    "고시": "고시",
    "지침": "고시",
}

HEADER_ALIASES = {
    "법규명": "law_name",
    "법령명": "law_name",
    "법종": "law_type",
    "관련조항": "article_display",
    "조문": "article_display",
    "조항": "article_display",
    "조문번호": "article_display",
    "주요내용": "summary_title",
    "요약": "summary_title",
    "해당부서": "department",
    "부서": "department",
    "실행내용": "action_required",
    "조치내용": "action_required",
    "대응대책": "countermeasure",
    "벌칙": "penalty",
    "벌칙 및 과태료": "penalty",
    "키워드": "keywords",
    "위험태그": "risk_tags",
    "작업유형태그": "work_type_tags",
    "문서태그": "document_tags",
    "시행일": "effective_date",
    "정렬순서": "sort_order",
    "비고": "notes",
}

SOURCE_FILE_CANDIDATES = (
    Path("data/legal_registry_import/법규등록부_탭구분_순번포함.txt"),
    Path("data/legal_registry_import/sample_법규등록부.tsv"),
    Path("data/legal_registry_import/법규등록부.json"),
    Path("data/legal_registry_import/법규등록부.csv"),
)


@dataclass
class ImportStats:
    law_masters_created: int = 0
    law_masters_updated: int = 0
    article_items_created: int = 0
    article_items_updated: int = 0
    revision_histories_created: int = 0
    revision_histories_updated: int = 0


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def coerce_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    text = normalize_text(value)
    if not text:
        return default
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def normalize_law_type(value: Any) -> str:
    raw = normalize_text(value).lower()
    if raw in LAW_TYPE_ALIASES:
        return LAW_TYPE_ALIASES[raw]
    if "시행령" in raw:
        return "령"
    if "시행규칙" in raw or raw.endswith("규칙"):
        return "규칙"
    if "고시" in raw or "지침" in raw:
        return "고시"
    return "법"


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = normalize_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def split_tags(value: Any) -> list[str]:
    raw = normalize_text(value)
    if not raw:
        return []
    normalized = raw.replace("|", ",").replace(";", ",").replace("/", ",")
    items: list[str] = []
    seen: set[str] = set()
    for part in normalized.split(","):
        token = normalize_text(part)
        if not token or token in seen:
            continue
        seen.add(token)
        items.append(token)
    return items


def join_tags(value: Any) -> str | None:
    items = split_tags(value)
    return ", ".join(items) if items else None


def build_article_search_text(payload: dict[str, Any]) -> str:
    parts = [
        payload.get("law_name"),
        payload.get("law_type"),
        payload.get("article_display"),
        payload.get("summary_title"),
        payload.get("department"),
        payload.get("action_required"),
        payload.get("countermeasure"),
        payload.get("penalty"),
        payload.get("keywords"),
        payload.get("risk_tags"),
        payload.get("work_type_tags"),
        payload.get("document_tags"),
    ]
    return " ".join(filter(None, (normalize_text(part) for part in parts))).strip()


def _header_key(value: str) -> str:
    compact = normalize_text(value).replace(" ", "")
    return HEADER_ALIASES.get(compact, "")


def _safe_part(parts: list[str], index: int) -> str:
    if index < 0 or index >= len(parts):
        return ""
    return normalize_text(parts[index])


def _append_text(base: str | None, extra: str | None) -> str | None:
    left = normalize_text(base)
    right = normalize_text(extra)
    if not right:
        return left or None
    if not left:
        return right
    return f"{left} {right}"


def _clean_law_name(value: Any) -> str:
    text = normalize_text(value)
    return text


def _infer_law_type_from_article_columns(article_cols: list[str], law_name: str) -> str:
    first = normalize_text(article_cols[0] if len(article_cols) > 0 else "")
    second = normalize_text(article_cols[1] if len(article_cols) > 1 else "")
    third = normalize_text(article_cols[2] if len(article_cols) > 2 else "")
    if third and not first and not second:
        return "규칙"
    if second and not first and not third:
        return "령"
    if first:
        return "법"
    return normalize_law_type(law_name)


def _load_records_from_structured_txt(source_file: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines = source_file.read_text(encoding="utf-8-sig").splitlines()
    article_records: list[dict[str, Any]] = []
    revision_records: list[dict[str, Any]] = []
    current_law_name = ""
    current_revision_date: str | None = None
    current_record: dict[str, Any] | None = None

    def flush_current_record() -> None:
        nonlocal current_record
        if current_record and normalize_text(current_record.get("summary_title")):
            current_record["search_text"] = build_article_search_text(current_record)
            article_records.append(current_record)
        current_record = None

    for raw_line in lines:
        parts = raw_line.split("\t")
        label = _safe_part(parts, 1)
        title_value = _safe_part(parts, 4)

        if label == "법규명" and title_value:
            flush_current_record()
            current_law_name = _clean_law_name(title_value)
            continue

        if label == "개정일":
            current_revision_date = title_value or None
            continue

        if label == "관련조항번호" or label in {"법", "영", "규칙"}:
            continue

        if not current_law_name:
            continue

        article_cols = [_safe_part(parts, 1), _safe_part(parts, 2), _safe_part(parts, 3)]
        article_display = " / ".join([col for col in article_cols if col]) or None
        summary_title = _safe_part(parts, 4) or None
        department = _safe_part(parts, 8) or None
        action_required = _safe_part(parts, 9) or None
        countermeasure = _safe_part(parts, 13) or None
        penalty = _safe_part(parts, 15) or None

        # 실제 TXT는 줄바꿈 이어쓰기 행이 섞여 있으므로, 숫자 line marker 없이 텍스트만 오면
        # 마지막 레코드의 action/penalty에 이어붙인다.
        if current_record and not article_display and not summary_title and not department and not action_required and not countermeasure and not penalty:
            leading_text = _safe_part(parts, 0)
            if leading_text and not leading_text.isdigit():
                current_record["action_required"] = _append_text(current_record.get("action_required"), leading_text)
            continue

        if current_record and not article_display and not summary_title and not department:
            leading_text = _safe_part(parts, 0)
            if leading_text and not leading_text.isdigit():
                current_record["action_required"] = _append_text(current_record.get("action_required"), leading_text)
            tail_text = ""
            for part in parts[1:]:
                token = normalize_text(part)
                if "벌금" in token or "과태료" in token or "징역" in token:
                    tail_text = token
                    break
            if tail_text:
                current_record["penalty"] = _append_text(current_record.get("penalty"), tail_text)
            continue

        if not any([article_display, summary_title, department, action_required, countermeasure, penalty]):
            continue

        flush_current_record()
        current_record = {
            "law_name": current_law_name,
            "law_type": _infer_law_type_from_article_columns(article_cols, current_law_name),
            "article_display": article_display,
            "summary_title": summary_title,
            "department": department,
            "action_required": action_required,
            "countermeasure": countermeasure,
            "penalty": penalty,
            "keywords": None,
            "risk_tags": None,
            "work_type_tags": None,
            "document_tags": None,
            "effective_date": None,
            "sort_order": 0,
            "notes": f"source_txt:{source_file.name}",
        }

        if current_revision_date:
            revision_records.append(
                {
                    "law_name": current_law_name,
                    "law_type": current_record["law_type"],
                    "revision_date": current_revision_date,
                    "revision_summary": summary_title,
                    "source_ref": article_display,
                    "parse_status": "imported_txt",
                }
            )

    flush_current_record()
    return article_records, revision_records


def _match_text(value: Any, needle: str) -> bool:
    haystack = normalize_text(value).lower()
    return bool(needle and haystack and needle in haystack)


def _matches_tag_filter(value: Any, needle: str | None) -> bool:
    if not needle:
        return True
    token = normalize_text(needle).lower()
    return any(token == item.lower() or token in item.lower() for item in split_tags(value))


def _score_article_query(master: LawMaster, article: LawArticleItem, query: str) -> float:
    normalized_query = normalize_text(query).lower()
    if not normalized_query:
        return 0.0
    tokens = [tok for tok in normalized_query.split(" ") if tok]
    targets = [
        (master.law_name, 5.0),
        (article.article_display, 4.0),
        (article.summary_title, 4.0),
        (article.action_required, 3.0),
        (article.keywords, 3.0),
        (article.search_text, 2.0),
    ]
    score = 0.0
    for text_value, weight in targets:
        value = normalize_text(text_value).lower()
        if not value:
            continue
        if normalized_query in value:
            score += weight + 1.0
        for token in tokens:
            if token in value:
                score += weight
    return round(score, 2)


def search_law_registry(
    db: Session,
    *,
    query: str = "",
    law_type: str | None = None,
    department: str | None = None,
    risk_tag: str | None = None,
    work_type_tag: str | None = None,
    document_tag: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    normalized_query = normalize_text(query)
    normalized_department = normalize_text(department)
    normalized_law_type = normalize_law_type(law_type) if law_type else None

    rows = (
        db.query(LawArticleItem, LawMaster)
        .join(LawMaster, LawArticleItem.law_master_id == LawMaster.id)
        .filter(LawArticleItem.is_active.is_(True))
        .all()
    )

    results: list[dict[str, Any]] = []
    for article, master in rows:
        if normalized_law_type and master.law_type != normalized_law_type:
            continue
        if normalized_department and not _match_text(article.department, normalized_department.lower()):
            continue
        if not _matches_tag_filter(article.risk_tags, risk_tag):
            continue
        if not _matches_tag_filter(article.work_type_tags, work_type_tag):
            continue
        if not _matches_tag_filter(article.document_tags, document_tag):
            continue

        relevance = _score_article_query(master, article, normalized_query)
        if normalized_query and relevance <= 0:
            continue
        if not normalized_query and not any([normalized_law_type, normalized_department, risk_tag, work_type_tag, document_tag]):
            continue

        results.append(
            {
                "law_master_id": master.id,
                "law_name": master.law_name,
                "law_type": master.law_type,
                "article_item_id": article.id,
                "article_display": article.article_display,
                "summary_title": article.summary_title,
                "action_required": article.action_required,
                "countermeasure": article.countermeasure,
                "penalty": article.penalty,
                "department": article.department,
                "risk_tags": split_tags(article.risk_tags),
                "work_type_tags": split_tags(article.work_type_tags),
                "document_tags": split_tags(article.document_tags),
                "relevance": relevance,
                "_sort_order": master.sort_order or 0,
                "_effective_date": master.effective_date.toordinal() if master.effective_date else 0,
            }
        )

    results.sort(
        key=lambda item: (
            item["relevance"],
            -item["_sort_order"],
            item["_effective_date"],
            -item["law_master_id"],
        ),
        reverse=True,
    )
    total = len(results)
    paged = results[max(0, offset) : max(0, offset) + max(1, limit)]
    for item in paged:
        item.pop("_sort_order", None)
        item.pop("_effective_date", None)
    return {
        "total": total,
        "limit": max(1, int(limit)),
        "offset": max(0, int(offset)),
        "items": paged,
    }


def upsert_law_master(
    db: Session,
    *,
    law_name: str,
    law_type: str | None = None,
    law_api_id: str | None = None,
    law_key: str | None = None,
    effective_date: Any = None,
    sort_order: int | None = None,
    notes: str | None = None,
) -> tuple[LawMaster, bool]:
    normalized_name = normalize_text(law_name)
    normalized_type = normalize_law_type(law_type or law_name)
    item = (
        db.query(LawMaster)
        .filter(
            func.lower(LawMaster.law_name) == normalized_name.lower(),
            LawMaster.law_type == normalized_type,
        )
        .first()
    )
    created = item is None
    if item is None:
        item = LawMaster(
            law_name=normalized_name,
            law_type=normalized_type,
        )
        db.add(item)

    item.law_api_id = normalize_text(law_api_id) or item.law_api_id
    item.law_key = normalize_text(law_key) or item.law_key
    item.effective_date = parse_date(effective_date) or item.effective_date
    item.sort_order = coerce_int(sort_order, item.sort_order or 0)
    item.notes = normalize_text(notes) or item.notes
    db.flush()
    return item, created


def upsert_article_item(db: Session, payload: dict[str, Any]) -> tuple[LawArticleItem, bool]:
    normalized_payload = dict(payload)
    normalized_payload["law_name"] = normalize_text(payload.get("law_name"))
    normalized_payload["law_type"] = normalize_law_type(payload.get("law_type") or payload.get("law_name"))
    normalized_payload["article_display"] = normalize_text(payload.get("article_display")) or None
    normalized_payload["summary_title"] = normalize_text(payload.get("summary_title")) or None
    normalized_payload["department"] = normalize_text(payload.get("department")) or None
    normalized_payload["action_required"] = normalize_text(payload.get("action_required")) or None
    normalized_payload["countermeasure"] = normalize_text(payload.get("countermeasure")) or None
    normalized_payload["penalty"] = normalize_text(payload.get("penalty")) or None
    normalized_payload["keywords"] = join_tags(payload.get("keywords"))
    normalized_payload["risk_tags"] = join_tags(payload.get("risk_tags"))
    normalized_payload["work_type_tags"] = join_tags(payload.get("work_type_tags"))
    normalized_payload["document_tags"] = join_tags(payload.get("document_tags"))

    master, _ = upsert_law_master(
        db,
        law_name=normalized_payload["law_name"],
        law_type=normalized_payload["law_type"],
        law_api_id=payload.get("law_api_id"),
        law_key=payload.get("law_key"),
        effective_date=payload.get("effective_date"),
        sort_order=payload.get("sort_order"),
        notes=payload.get("notes"),
    )

    item = (
        db.query(LawArticleItem)
        .filter(
            LawArticleItem.law_master_id == master.id,
            LawArticleItem.article_display == normalized_payload["article_display"],
            LawArticleItem.summary_title == normalized_payload["summary_title"],
        )
        .first()
    )
    created = item is None
    if item is None:
        item = LawArticleItem(law_master_id=master.id)
        db.add(item)

    item.article_display = normalized_payload["article_display"]
    item.summary_title = normalized_payload["summary_title"]
    item.department = normalized_payload["department"]
    item.action_required = normalized_payload["action_required"]
    item.countermeasure = normalized_payload["countermeasure"]
    item.penalty = normalized_payload["penalty"]
    item.keywords = normalized_payload["keywords"]
    item.risk_tags = normalized_payload["risk_tags"]
    item.work_type_tags = normalized_payload["work_type_tags"]
    item.document_tags = normalized_payload["document_tags"]
    item.is_active = bool(payload.get("is_active", True))
    item.search_text = build_article_search_text(normalized_payload)
    db.flush()
    return item, created


def upsert_revision_history(db: Session, payload: dict[str, Any]) -> tuple[LawRevisionHistory, bool]:
    master, _ = upsert_law_master(
        db,
        law_name=payload.get("law_name") or "",
        law_type=payload.get("law_type"),
        law_api_id=payload.get("law_api_id"),
        law_key=payload.get("law_key"),
        effective_date=payload.get("effective_date"),
        sort_order=payload.get("sort_order"),
        notes=payload.get("notes"),
    )
    revision_date = parse_date(payload.get("revision_date"))
    revision_summary = normalize_text(payload.get("revision_summary")) or None
    item = (
        db.query(LawRevisionHistory)
        .filter(
            LawRevisionHistory.law_master_id == master.id,
            LawRevisionHistory.revision_date == revision_date,
            LawRevisionHistory.revision_summary == revision_summary,
        )
        .first()
    )
    created = item is None
    if item is None:
        item = LawRevisionHistory(law_master_id=master.id)
        db.add(item)
    item.revision_date = revision_date
    item.revision_summary = revision_summary
    item.source_ref = normalize_text(payload.get("source_ref")) or None
    item.parse_status = normalize_text(payload.get("parse_status")) or None
    db.flush()
    return item, created


def import_records(
    db: Session,
    *,
    article_records: list[dict[str, Any]],
    revision_records: list[dict[str, Any]] | None = None,
) -> ImportStats:
    stats = ImportStats()
    seen_master_keys: set[tuple[str, str]] = set()

    for record in article_records:
        master, master_created = upsert_law_master(
            db,
            law_name=record.get("law_name") or "",
            law_type=record.get("law_type"),
            law_api_id=record.get("law_api_id"),
            law_key=record.get("law_key"),
            effective_date=record.get("effective_date"),
            sort_order=record.get("sort_order"),
            notes=record.get("notes"),
        )
        master_key = (master.law_name, master.law_type)
        if master_key not in seen_master_keys:
            seen_master_keys.add(master_key)
            if master_created:
                stats.law_masters_created += 1
            else:
                stats.law_masters_updated += 1

        _, article_created = upsert_article_item(db, record)
        if article_created:
            stats.article_items_created += 1
        else:
            stats.article_items_updated += 1

    for record in revision_records or []:
        item, created = upsert_revision_history(db, record)
        if created:
            stats.revision_histories_created += 1
        else:
            stats.revision_histories_updated += 1

    db.commit()
    return stats


def detect_source_file(project_root: Path) -> Path | None:
    for relative_path in SOURCE_FILE_CANDIDATES:
        candidate = project_root / relative_path
        if candidate.is_file():
            return candidate
    return None


def load_records_from_tsv_or_csv(source_file: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    delimiter = "\t" if source_file.suffix.lower() in {".tsv", ".txt"} else ","
    if source_file.suffix.lower() == ".txt":
        first_chunk = source_file.read_text(encoding="utf-8-sig").splitlines()[:5]
        if not any("순번" in normalize_text(line) for line in first_chunk):
            return _load_records_from_structured_txt(source_file)

    lines = source_file.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        return [], []

    first_line = lines[0]
    header_keys = [_header_key(part) for part in first_line.split(delimiter)]
    article_records: list[dict[str, Any]] = []

    if any(header_keys):
        with source_file.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            for row in reader:
                mapped: dict[str, Any] = {}
                for key, value in row.items():
                    normalized_key = _header_key(key or "") or normalize_text(key)
                    mapped[normalized_key] = value
                law_name = normalize_text(mapped.get("law_name"))
                if not law_name:
                    continue
                article_records.append(
                    {
                        "law_name": law_name,
                        "law_type": mapped.get("law_type") or law_name,
                        "article_display": mapped.get("article_display"),
                        "summary_title": mapped.get("summary_title"),
                        "department": mapped.get("department"),
                        "action_required": mapped.get("action_required"),
                        "countermeasure": mapped.get("countermeasure"),
                        "penalty": mapped.get("penalty"),
                        "keywords": mapped.get("keywords"),
                        "risk_tags": mapped.get("risk_tags"),
                        "work_type_tags": mapped.get("work_type_tags"),
                        "document_tags": mapped.get("document_tags"),
                        "effective_date": mapped.get("effective_date"),
                        "sort_order": mapped.get("sort_order") or 0,
                        "notes": mapped.get("notes"),
                    }
                )
        return article_records, []

    for line in lines:
        if not normalize_text(line):
            continue
        cols = [part.strip() for part in line.split(delimiter)]
        if len(cols) < 8:
            continue
        article_records.append(
            {
                "law_name": cols[1],
                "law_type": cols[1],
                "article_display": cols[2],
                "summary_title": cols[3],
                "department": cols[4],
                "action_required": cols[5],
                "countermeasure": cols[6],
                "penalty": cols[7],
                "sort_order": cols[0] or 0,
            }
        )
    return article_records, []


def load_records_from_json(source_file: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads(source_file.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        return payload.get("article_records", []), payload.get("revision_records", [])
    if isinstance(payload, list):
        return payload, []
    return [], []


def load_records_from_sqlite(source_db_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    article_records: list[dict[str, Any]] = []
    revision_records: list[dict[str, Any]] = []
    conn = sqlite3.connect(source_db_path)
    conn.row_factory = sqlite3.Row
    try:
        table_names = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        if "law_master" not in table_names or "law_article_item" not in table_names:
            raise RuntimeError("source sqlite does not contain law_master / law_article_item tables")

        article_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(law_article_item)").fetchall()
        }
        revision_columns = (
            {
                row["name"]
                for row in conn.execute("PRAGMA table_info(law_revision_history)").fetchall()
            }
            if "law_revision_history" in table_names
            else set()
        )

        def article_expr(column_name: str, alias: str | None = None) -> str:
            name = alias or column_name
            if column_name in article_columns:
                return f"a.{column_name} AS {name}"
            return f"NULL AS {name}"

        article_query = """
            SELECT
                m.law_name,
                m.law_type,
                m.law_api_id,
                m.law_key,
                m.effective_date,
                m.sort_order,
                m.notes,
                {article_display},
                {summary_title},
                {department},
                {action_required},
                {countermeasure},
                {penalty},
                {keywords},
                {risk_tags},
                {work_type_tags},
                {document_tags},
                {is_active}
            FROM law_article_item a
            JOIN law_master m ON m.id = a.law_master_id
        """.format(
            article_display=article_expr("article_display"),
            summary_title=article_expr("summary_title"),
            department=article_expr("department"),
            action_required=article_expr("action_required"),
            countermeasure=article_expr("countermeasure"),
            penalty=article_expr("penalty"),
            keywords=article_expr("keywords"),
            risk_tags=article_expr("risk_tags"),
            work_type_tags=article_expr("work_type_tags"),
            document_tags=article_expr("document_tags"),
            is_active=article_expr("is_active"),
        )
        article_records = [dict(row) for row in conn.execute(article_query).fetchall()]

        if "law_revision_history" in table_names:
            def revision_expr(primary: str, fallback: str | None = None, alias: str | None = None) -> str:
                name = alias or primary
                if primary in revision_columns:
                    return f"r.{primary} AS {name}"
                if fallback and fallback in revision_columns:
                    return f"r.{fallback} AS {name}"
                return f"NULL AS {name}"

            revision_query = """
                SELECT
                    m.law_name,
                    m.law_type,
                    m.law_api_id,
                    m.law_key,
                    {revision_date},
                    {revision_summary},
                    {source_ref},
                    {parse_status}
                FROM law_revision_history r
                JOIN law_master m ON m.id = r.law_master_id
            """.format(
                revision_date=revision_expr("revision_date", "amendment_date", "revision_date"),
                revision_summary=revision_expr("revision_summary", "main_content", "revision_summary"),
                source_ref=revision_expr("source_ref", "related_articles", "source_ref"),
                parse_status=revision_expr("parse_status", "review_status", "parse_status"),
            )
            revision_records = [dict(row) for row in conn.execute(revision_query).fetchall()]
    finally:
        conn.close()
    return article_records, revision_records


def _table_exists_postgres(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return cursor.fetchone() is not None


def _postgres_columns(cursor, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return {row[0] for row in cursor.fetchall()}


def load_records_from_postgres(source_db_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("psycopg2 is not installed; pass a TSV/CSV/JSON source instead") from exc

    parsed = urlparse(source_db_url)
    conn = psycopg2.connect(
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
    )
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            if not _table_exists_postgres(cursor, "law_master") or not _table_exists_postgres(cursor, "law_article_item"):
                raise RuntimeError("source postgres does not contain law_master / law_article_item tables")

            article_columns = _postgres_columns(cursor, "law_article_item")
            revision_columns = (
                _postgres_columns(cursor, "law_revision_history")
                if _table_exists_postgres(cursor, "law_revision_history")
                else set()
            )

            def article_expr(column_name: str, alias: str | None = None) -> str:
                name = alias or column_name
                if column_name in article_columns:
                    return f"a.{column_name} AS {name}"
                return f"NULL AS {name}"

            cursor.execute(
                """
                SELECT
                    m.law_name,
                    m.law_type,
                    m.law_api_id,
                    m.law_key,
                    m.effective_date,
                    m.sort_order,
                    m.notes,
                    {article_display},
                    {summary_title},
                    {department},
                    {action_required},
                    {countermeasure},
                    {penalty},
                    {keywords},
                    {risk_tags},
                    {work_type_tags},
                    {document_tags},
                    {is_active}
                FROM law_article_item a
                JOIN law_master m ON m.id = a.law_master_id
                """
                .format(
                    article_display=article_expr("article_display"),
                    summary_title=article_expr("summary_title"),
                    department=article_expr("department"),
                    action_required=article_expr("action_required"),
                    countermeasure=article_expr("countermeasure"),
                    penalty=article_expr("penalty"),
                    keywords=article_expr("keywords"),
                    risk_tags=article_expr("risk_tags"),
                    work_type_tags=article_expr("work_type_tags"),
                    document_tags=article_expr("document_tags"),
                    is_active=article_expr("is_active"),
                )
            )
            article_records = [dict(row) for row in cursor.fetchall()]

            revision_records: list[dict[str, Any]] = []
            if _table_exists_postgres(cursor, "law_revision_history"):
                def revision_expr(primary: str, fallback: str | None = None, alias: str | None = None) -> str:
                    name = alias or primary
                    if primary in revision_columns:
                        return f"r.{primary} AS {name}"
                    if fallback and fallback in revision_columns:
                        return f"r.{fallback} AS {name}"
                    return f"NULL AS {name}"

                cursor.execute(
                    """
                    SELECT
                        m.law_name,
                        m.law_type,
                        m.law_api_id,
                        m.law_key,
                        {revision_date},
                        {revision_summary},
                        {source_ref},
                        {parse_status}
                    FROM law_revision_history r
                    JOIN law_master m ON m.id = r.law_master_id
                    """
                    .format(
                        revision_date=revision_expr("revision_date", "amendment_date", "revision_date"),
                        revision_summary=revision_expr("revision_summary", "main_content", "revision_summary"),
                        source_ref=revision_expr("source_ref", "related_articles", "source_ref"),
                        parse_status=revision_expr("parse_status", "review_status", "parse_status"),
                    )
                )
                revision_records = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
    return article_records, revision_records
