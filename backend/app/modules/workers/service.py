from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Literal, Sequence

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.utils.file_ingestion import (
    IngestionPipelineError,
    open_xlrd_workbook,
    parse_excel_with_fallback,
    validate_worker_file_structure,
)
from app.modules.workers.models import (
    Employment,
    Person,
    WorkerImportBatch,
    WorkerInactiveCandidate,
)

logger = logging.getLogger(__name__)


class WorkerIngestionError(ValueError):
    def __init__(self, message: str, ingestion: dict[str, Any] | None = None):
        super().__init__(message)
        self.ingestion = ingestion or {}


@dataclass
class WorkerDiffItemDTO:
    type: Literal["NEW", "UPDATED", "UNCHANGED"]
    person_id: int | None
    changes: dict[str, tuple[Any, Any]] | None
    row: dict[str, Any]


@dataclass
class WorkerDiffResult:
    items: list[WorkerDiffItemDTO]
    missing_count: int = 0
    missing_sample: list[dict[str, Any]] | None = None

    @property
    def new_items(self) -> list[WorkerDiffItemDTO]:
        return [i for i in self.items if i.type == "NEW"]

    @property
    def updated_items(self) -> list[WorkerDiffItemDTO]:
        return [i for i in self.items if i.type == "UPDATED"]

    @property
    def unchanged_items(self) -> list[WorkerDiffItemDTO]:
        return [i for i in self.items if i.type == "UNCHANGED"]


def _excel_scalar_to_code(v: Any) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    s = str(v).strip()
    return s if s else None


def _employee_row_to_dict(values: Sequence[Any]) -> dict[str, Any] | None:
    """
    employees_raw / 사원리스트 공통 그리드(헤더 제외 데이터 행).
    0 성명, 1 입사일, 2 고용형태, 3 부서, 4 사원코드, 5 직위, 6~7 주민번호, … 18~20 휴대폰, 13 국적
    """
    vals = list(values)
    if len(vals) < 21:
        vals.extend([None] * (21 - len(vals)))
    if not any(vals):
        return None
    name_raw = vals[0]
    name = str(name_raw).strip() if name_raw is not None else ""
    rrn_front = vals[6]
    rrn_back = vals[7]
    phone1, phone2, phone3 = vals[18], vals[19], vals[20]
    nationality = vals[13]
    department_code = _excel_scalar_to_code(vals[3])
    employee_code = _excel_scalar_to_code(vals[4])
    position_code = _excel_scalar_to_code(vals[5])
    site_code = None
    is_active = True
    if not rrn_front or not rrn_back:
        return None
    rrn_raw = f"{str(rrn_front).strip()}{str(rrn_back).strip()}"
    rrn_hash = _hash_rrn(rrn_raw)
    phone_mobile = _normalize_phone_parts(phone1, phone2, phone3)
    return {
        "name": name,
        "rrn_hash": rrn_hash,
        "phone_mobile": phone_mobile,
        "nationality": nationality,
        "department_code": department_code,
        "employee_code": employee_code,
        "position_code": position_code,
        "site_code": site_code,
        "is_active": is_active,
    }


def _load_employees_rows_from_xlsx(
    path: Path,
    *,
    include_ingestion: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        parsed = parse_excel_with_fallback(path)
    except IngestionPipelineError as exc:
        raise WorkerIngestionError("파일을 파싱할 수 없습니다.", ingestion=exc.diagnostics)
    validation = validate_worker_file_structure(
        parsed.headers,
        required_columns=["성   명", "사원코드", "직위", "주민번호", "휴대폰"],
    )
    warnings: list[str] = []
    if not validation["required_columns_ok"]:
        warnings.append("Header row not recognized")
    ingestion = parsed.to_public_diagnostics(
        header_valid=validation["required_columns_ok"],
        warnings=warnings,
    )
    logger.info(
        "worker ingestion diagnostics: %s",
        {
            "file_type": parsed.file_type,
            "parser_used": parsed.parser_used,
            "fallback_used": parsed.fallback_used,
            "row_count": parsed.row_count,
            "required_columns_ok": validation["required_columns_ok"],
            "missing_required_columns": validation["missing_required_columns"],
        },
    )
    if not parsed.headers:
        ingestion["warnings"] = list(set([*ingestion.get("warnings", []), "Header row not recognized"]))
        raise WorkerIngestionError(
            "파일 구조를 인식할 수 없습니다. 헤더를 확인해 주세요.",
            ingestion=ingestion,
        )
    if not parsed.rows:
        ingestion["warnings"] = list(set([*ingestion.get("warnings", []), "No data rows found"]))
        raise WorkerIngestionError(
            "파일 구조는 읽혔으나 데이터가 비어 있습니다.",
            ingestion=ingestion,
        )

    # 컬럼 인덱스는 기존 employees_raw 구조 기준(헤더 깨짐 파일 호환)
    max_col = max(len(parsed.headers), max((len(r) for r in parsed.rows), default=0))
    if max_col < 21:
        ingestion["warnings"] = list(set([*ingestion.get("warnings", []), "Header row not recognized"]))
        raise WorkerIngestionError(
            "파일 구조를 인식할 수 없습니다. 헤더를 확인해 주세요.",
            ingestion=ingestion,
        )

    rows: list[dict[str, Any]] = []
    for values in parsed.rows:
        row_dict = _employee_row_to_dict(values)
        if row_dict:
            rows.append(row_dict)
    if include_ingestion:
        return rows, ingestion
    return rows


def _hash_rrn(rrn_raw: str) -> str:
    # 간단한 해시 구현 (실제에선 SHA-256 등 사용)
    import hashlib

    return hashlib.sha256(rrn_raw.encode("utf-8")).hexdigest()


def _normalize_phone_parts(p1: Any, p2: Any, p3: Any) -> str | None:
    parts = []
    for p in (p1, p2, p3):
        if p is None:
            continue
        s = str(p).strip()
        if not s:
            continue
        parts.append(s)
    if not parts:
        return None
    digits = "".join(ch for part in parts for ch in part if ch.isdigit())
    if len(digits) < 9:
        return None
    return digits


def _build_baseline_map(db: Session) -> dict[str, tuple[Person, Employment | None]]:
    persons = {p.rrn_hash: p for p in db.query(Person).all() if p.rrn_hash}
    emps_by_person: dict[int, Employment | None] = {}
    q = db.query(Employment).filter(Employment.source_type == "employee")
    for e in q.all():
        if e.person_id not in emps_by_person:
            emps_by_person[e.person_id] = e
    result: dict[str, tuple[Person, Employment | None]] = {}
    for rrn_hash, person in persons.items():
        emp = emps_by_person.get(person.id)
        result[rrn_hash] = (person, emp)
    return result


def compute_worker_diff(
    new_rows: list[dict[str, Any]],
    baseline: dict[str, tuple[Person, Employment | None]],
    active_baseline_summary: dict[str, dict[str, Any]] | None = None,
) -> WorkerDiffResult:
    items: list[WorkerDiffItemDTO] = []
    new_rrn_hashes: set[str] = set()

    for row in new_rows:
        rrn_hash = row.get("rrn_hash")
        if not rrn_hash:
            continue
        new_rrn_hashes.add(rrn_hash)
        base = baseline.get(rrn_hash)
        if base is None:
            items.append(WorkerDiffItemDTO("NEW", None, None, row))
            continue
        person, emp = base
        changes: dict[str, tuple[Any, Any]] = {}
        # Person fields
        if row.get("name") is not None and row["name"] != person.name:
            changes["name"] = (person.name, row["name"])
        if row.get("phone_mobile") is not None and row["phone_mobile"] != person.phone_mobile:
            changes["phone_mobile"] = (person.phone_mobile, row["phone_mobile"])
        if row.get("nationality") is not None and row["nationality"] != person.nationality:
            changes["nationality"] = (person.nationality, row["nationality"])
        # Employment fields
        if emp is not None:
            if (
                row.get("department_code") is not None
                and row["department_code"] != emp.department_code
            ):
                changes["department_code"] = (emp.department_code, row["department_code"])
            if row.get("employee_code") is not None and row["employee_code"] != (emp.employee_code or None):
                changes["employee_code"] = (emp.employee_code, row["employee_code"])
            if (
                row.get("position_code") is not None
                and row["position_code"] != emp.position_code
            ):
                changes["position_code"] = (emp.position_code, row["position_code"])
            if row.get("site_code") is not None and row["site_code"] != emp.site_code:
                changes["site_code"] = (emp.site_code, row["site_code"])
            if row.get("is_active") is not None and row["is_active"] != emp.is_active:
                changes["is_active"] = (emp.is_active, row["is_active"])
        if changes:
            items.append(WorkerDiffItemDTO("UPDATED", person.id, changes, row))
        else:
            items.append(WorkerDiffItemDTO("UNCHANGED", person.id, None, row))

    missing_count = 0
    missing_sample: list[dict[str, Any]] = []
    if active_baseline_summary is not None:
        baseline_set = set(active_baseline_summary.keys())
        missing_rrn_hashes = baseline_set - new_rrn_hashes
        missing_count = len(missing_rrn_hashes)
        for rrn in list(missing_rrn_hashes)[:10]:
            info = active_baseline_summary.get(rrn, {})
            missing_sample.append(
                {
                    "person_id": info.get("person_id"),
                    "name": info.get("name"),
                    "phone_mobile": info.get("phone_mobile"),
                    "rrn_hash": rrn,
                }
            )

    return WorkerDiffResult(
        items=items,
        missing_count=missing_count,
        missing_sample=missing_sample,
    )


def diff_employees_from_path(db: Session, path: Path) -> WorkerDiffResult:
    new_rows = _load_employees_rows_from_xlsx(path)
    baseline = _build_baseline_map(db)

    # 활성 Employment 기준 baseline 요약 (누락자 계산용)
    active_baseline_summary: dict[str, dict[str, Any]] = {}
    from app.modules.workers.models import Employment as EmpModel, Person as PersonModel

    q = (
        db.query(
            PersonModel.rrn_hash,
            PersonModel.id,
            EmpModel.id,
            PersonModel.name,
            PersonModel.phone_mobile,
        )
        .join(EmpModel, EmpModel.person_id == PersonModel.id)
        .filter(
            EmpModel.source_type == "employee",
            EmpModel.is_active.is_(True),
            PersonModel.rrn_hash.isnot(None),
        )
    )
    for rrn_hash, person_id, employment_id, name, phone_mobile in q.all():
        if rrn_hash and rrn_hash not in active_baseline_summary:
            active_baseline_summary[rrn_hash] = {
                "person_id": person_id,
                "employment_id": employment_id,
                "name": name,
                "phone_mobile": phone_mobile,
            }

    diff = compute_worker_diff(new_rows, baseline, active_baseline_summary)

    # WorkerInactiveCandidate 생성/갱신/해제
    new_rrn_hashes: set[str] = {
        row["rrn_hash"] for row in new_rows if row.get("rrn_hash") is not None
    }
    baseline_set = set(active_baseline_summary.keys())
    missing_rrn_hashes = baseline_set - new_rrn_hashes

    if baseline_set:
        all_rrn_for_candidates = list(baseline_set | new_rrn_hashes)
        existing_candidates = {
            c.rrn_hash: c
            for c in db.query(WorkerInactiveCandidate)
            .filter(WorkerInactiveCandidate.rrn_hash.in_(all_rrn_for_candidates))
            .all()
        }

        # 누락자 → 후보 생성/갱신
        for rrn in missing_rrn_hashes:
            info = active_baseline_summary.get(rrn)
            if not info:
                continue
            cand = existing_candidates.get(rrn)
            if cand is None:
                cand = WorkerInactiveCandidate(
                    person_id=info.get("person_id"),
                    employment_id=info.get("employment_id"),
                    rrn_hash=rrn,
                    source_type="employee",
                    status="CANDIDATE",
                    missing_streak=1,
                )
                db.add(cand)
                existing_candidates[rrn] = cand
            else:
                # 이전 상태와 무관하게 누락이 반복되면 streak 증가
                cand.missing_streak = (cand.missing_streak or 0) + 1
                # RESOLVED 였다면 다시 후보로 되돌림
                if cand.status == "RESOLVED":
                    cand.status = "CANDIDATE"
                    cand.resolution = None

        # 재등장 → 후보 해제(RESOLVED)
        reappeared_rrn = new_rrn_hashes & set(existing_candidates.keys())
        for rrn in reappeared_rrn:
            cand = existing_candidates.get(rrn)
            if cand is None:
                continue
            if cand.status != "RESOLVED":
                cand.status = "RESOLVED"
                cand.resolution = "FALSE_MISSING"

        db.commit()

    return diff


def diff_employees_from_path_with_ingestion(
    db: Session,
    path: Path,
) -> tuple[WorkerDiffResult, dict[str, Any]]:
    new_rows, ingestion = _load_employees_rows_from_xlsx(path, include_ingestion=True)
    baseline = _build_baseline_map(db)
    active_baseline_summary: dict[str, dict[str, Any]] = {}
    from app.modules.workers.models import Employment as EmpModel, Person as PersonModel

    q = (
        db.query(
            PersonModel.rrn_hash,
            PersonModel.id,
            EmpModel.id,
            PersonModel.name,
            PersonModel.phone_mobile,
        )
        .join(EmpModel, EmpModel.person_id == PersonModel.id)
        .filter(
            EmpModel.source_type == "employee",
            EmpModel.is_active.is_(True),
            PersonModel.rrn_hash.isnot(None),
        )
    )
    for rrn_hash, person_id, employment_id, name, phone_mobile in q.all():
        if rrn_hash and rrn_hash not in active_baseline_summary:
            active_baseline_summary[rrn_hash] = {
                "person_id": person_id,
                "employment_id": employment_id,
                "name": name,
                "phone_mobile": phone_mobile,
            }

    diff = compute_worker_diff(new_rows, baseline, active_baseline_summary)

    new_rrn_hashes: set[str] = {
        row["rrn_hash"] for row in new_rows if row.get("rrn_hash") is not None
    }
    baseline_set = set(active_baseline_summary.keys())
    missing_rrn_hashes = baseline_set - new_rrn_hashes

    if baseline_set:
        all_rrn_for_candidates = list(baseline_set | new_rrn_hashes)
        existing_candidates = {
            c.rrn_hash: c
            for c in db.query(WorkerInactiveCandidate)
            .filter(WorkerInactiveCandidate.rrn_hash.in_(all_rrn_for_candidates))
            .all()
        }

        for rrn in missing_rrn_hashes:
            info = active_baseline_summary.get(rrn)
            if not info:
                continue
            cand = existing_candidates.get(rrn)
            if cand is None:
                cand = WorkerInactiveCandidate(
                    person_id=info.get("person_id"),
                    employment_id=info.get("employment_id"),
                    rrn_hash=rrn,
                    source_type="employee",
                    status="CANDIDATE",
                    missing_streak=1,
                )
                db.add(cand)
                existing_candidates[rrn] = cand
            else:
                cand.missing_streak = (cand.missing_streak or 0) + 1
                if cand.status == "RESOLVED":
                    cand.status = "CANDIDATE"
                    cand.resolution = None

        reappeared_rrn = new_rrn_hashes & set(existing_candidates.keys())
        for rrn in reappeared_rrn:
            cand = existing_candidates.get(rrn)
            if cand is None:
                continue
            if cand.status != "RESOLVED":
                cand.status = "RESOLVED"
                cand.resolution = "FALSE_MISSING"

        db.commit()

    return diff, ingestion


def apply_worker_diff(
    db: Session,
    diff: WorkerDiffResult,
    apply_new: bool,
    apply_updated: bool,
    source_type: str,
    original_filename: str,
) -> WorkerImportBatch:
    total = len(diff.items)
    applied_new = 0
    applied_updated = 0
    for item in diff.items:
        if item.type == "NEW" and apply_new:
            row = item.row
            person = Person(
                name=row.get("name") or "",
                rrn_hash=row.get("rrn_hash"),
                phone_mobile=row.get("phone_mobile"),
                nationality=row.get("nationality"),
            )
            db.add(person)
            db.flush()
            emp = Employment(
                person_id=person.id,
                source_type="employee",
                employee_code=row.get("employee_code"),
                department_code=row.get("department_code"),
                position_code=row.get("position_code"),
                site_code=row.get("site_code"),
                is_active=row.get("is_active", True),
            )
            db.add(emp)
            applied_new += 1
        elif item.type == "UPDATED" and apply_updated and item.person_id is not None:
            person = db.query(Person).filter(Person.id == item.person_id).first()
            emp = (
                db.query(Employment)
                .filter(
                    Employment.person_id == item.person_id,
                    Employment.source_type == "employee",
                )
                .first()
            )
            if person is None:
                continue
            for field, (old, new) in item.changes.items():
                if field in {"name", "phone_mobile", "nationality"}:
                    setattr(person, field, new)
                elif emp is not None and field in {
                    "department_code",
                    "employee_code",
                    "position_code",
                    "site_code",
                    "is_active",
                }:
                    setattr(emp, field, new)
            applied_updated += 1
    batch = WorkerImportBatch(
        source_type=source_type,
        original_filename=original_filename,
        stored_path=str(Path(settings.sqlite_path).name),
        total_rows=total,
        created_rows=applied_new,
        updated_rows=applied_updated,
        failed_rows=0,
        warning_summary=None,
        diff_new_count=len(diff.new_items),
        diff_updated_count=len(diff.updated_items),
        diff_unchanged_count=len(diff.unchanged_items),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def _upsert_employees_from_row_dicts(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    original_filename: str,
    stored_path: str,
    source_type: str,
) -> WorkerImportBatch:
    total = len(rows)
    created = 0
    updated = 0
    failed = 0
    existing_persons = {p.rrn_hash: p for p in db.query(Person).all() if p.rrn_hash}

    for row in rows:
        rrn_hash = row.get("rrn_hash")
        if not rrn_hash:
            failed += 1
            continue

        person = existing_persons.get(rrn_hash)
        if person is None:
            person = Person(
                name=row.get("name") or "",
                rrn_hash=rrn_hash,
                phone_mobile=row.get("phone_mobile"),
                nationality=row.get("nationality"),
            )
            db.add(person)
            db.flush()
            existing_persons[rrn_hash] = person
            created += 1
        else:
            if row.get("name"):
                person.name = row["name"]
            if row.get("phone_mobile"):
                person.phone_mobile = row["phone_mobile"]
            if row.get("nationality"):
                person.nationality = row["nationality"]
            updated += 1

        emp = (
            db.query(Employment)
            .filter(
                Employment.person_id == person.id,
                Employment.source_type == "employee",
            )
            .first()
        )
        if emp is None:
            emp = Employment(
                person_id=person.id,
                source_type="employee",
                employee_code=row.get("employee_code"),
                department_code=row.get("department_code"),
                position_code=row.get("position_code"),
                site_code=row.get("site_code"),
                is_active=row.get("is_active", True),
            )
            db.add(emp)
        else:
            if row.get("department_code") is not None:
                emp.department_code = row["department_code"]
            if row.get("employee_code") is not None:
                emp.employee_code = row["employee_code"]
            if row.get("position_code") is not None:
                emp.position_code = row["position_code"]
            if row.get("site_code") is not None:
                emp.site_code = row["site_code"]
            if row.get("is_active") is not None:
                emp.is_active = row["is_active"]

    batch = WorkerImportBatch(
        source_type=source_type,
        original_filename=original_filename,
        stored_path=stored_path,
        total_rows=total,
        created_rows=created,
        updated_rows=updated,
        failed_rows=failed,
        warning_summary=None,
        diff_new_count=0,
        diff_updated_count=0,
        diff_unchanged_count=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def _employee_dicts_from_parsed_data_rows(parsed_rows: list[list[Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for values in parsed_rows:
        d = _employee_row_to_dict(values)
        if d:
            out.append(d)
    return out


def _load_sawon_employee_row_dicts(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    사원리스트(.xls/.xlsx). 1차 parse_excel_with_fallback, 실패·0건 시 xlrd 직접,
    그다음 .xls → 임시 xlsx 변환 후 재파싱.
    """
    ingestion: dict[str, Any] = {"warnings": [], "conversion_applied": None}
    row_dicts: list[dict[str, Any]] = []

    try:
        parsed = parse_excel_with_fallback(path)
        validation = validate_worker_file_structure(
            parsed.headers,
            required_columns=["성   명", "사원코드", "직위", "주민번호", "휴대폰"],
        )
        ing = parsed.to_public_diagnostics(
            header_valid=validation["required_columns_ok"],
            warnings=[] if validation["required_columns_ok"] else ["required header columns missing"],
        )
        ingestion.update(ing)
        row_dicts = _employee_dicts_from_parsed_data_rows(parsed.rows)
    except Exception as exc:  # noqa: BLE001
        ingestion["primary_parse_error"] = str(exc)

    if not row_dicts:
        try:
            wb = open_xlrd_workbook(path)
            sh = wb.sheet_by_index(0)
            raw_rows: list[list[Any]] = []
            for r in range(sh.nrows):
                raw_rows.append([sh.cell_value(r, c) for c in range(sh.ncols)])
            if raw_rows:
                h0 = str(raw_rows[0][0]).strip() if raw_rows[0] else ""
                compact = h0.replace(" ", "")
                body = raw_rows[1:] if ("성" in h0 and "명" in compact) else raw_rows
                for values in body:
                    d = _employee_row_to_dict(values)
                    if d:
                        row_dicts.append(d)
            ingestion["conversion_applied"] = "xlrd_sheet_full_read"
        except Exception as exc2:  # noqa: BLE001
            ingestion["xlrd_read_error"] = str(exc2)

    if not row_dicts and path.suffix.lower() == ".xls":
        try:
            import openpyxl

            wb_x = open_xlrd_workbook(path)
            sh = wb_x.sheet_by_index(0)
            nwb = openpyxl.Workbook()
            ws = nwb.active
            for r in range(sh.nrows):
                ws.append([sh.cell_value(r, c) for c in range(sh.ncols)])
            conv_dir = settings.storage_root / "sawon_converted"
            conv_dir.mkdir(parents=True, exist_ok=True)
            conv_path = conv_dir / f"{path.stem}_converted.xlsx"
            nwb.save(conv_path)
            parsed = parse_excel_with_fallback(conv_path)
            row_dicts = _employee_dicts_from_parsed_data_rows(parsed.rows)
            ingestion["conversion_applied"] = "xls_to_xlsx_then_parse_excel"
            ingestion["converted_path"] = str(conv_path)
        except Exception as exc3:  # noqa: BLE001
            ingestion["xls_to_xlsx_error"] = str(exc3)

    return row_dicts, ingestion


def import_sawon_list_from_path(db: Session, path: Path) -> tuple[WorkerImportBatch, dict[str, Any]]:
    row_dicts, ingestion = _load_sawon_employee_row_dicts(path)
    if not row_dicts:
        raise WorkerIngestionError(
            "사원리스트에서 직원 데이터 행을 찾을 수 없습니다. 열 구조(성명·부서·사원코드·직위·주민번호·휴대폰)를 확인하세요.",
            ingestion=ingestion,
        )
    batch = _upsert_employees_from_row_dicts(
        db,
        row_dicts,
        original_filename=path.name,
        stored_path=str(path),
        source_type="sawon_list_upload",
    )
    ingestion["imported_employee_rows"] = len(row_dicts)
    return batch, ingestion


def import_employees_from_path(db: Session, path: Path) -> WorkerImportBatch:
    """
    employees_raw.xlsx 포맷을 baseline/일반 import용으로 처리.
    기존 DB 상태와 무관하게, 파일 내용 기준으로 Person/Employment를 upsert한다.
    """
    rows = _load_employees_rows_from_xlsx(path)
    return _upsert_employees_from_row_dicts(
        db,
        rows,
        original_filename=path.name,
        stored_path=str(path),
        source_type="employees_import",
    )


def import_employees_from_path_with_ingestion(
    db: Session,
    path: Path,
) -> tuple[WorkerImportBatch, dict[str, Any]]:
    rows, ingestion = _load_employees_rows_from_xlsx(path, include_ingestion=True)
    batch = _upsert_employees_from_row_dicts(
        db,
        rows,
        original_filename=path.name,
        stored_path=str(path),
        source_type="employees_import",
    )
    return batch, ingestion

