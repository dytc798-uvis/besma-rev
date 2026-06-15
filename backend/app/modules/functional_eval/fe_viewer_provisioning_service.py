"""본사 기능인인정제 조회전용 계정 일괄 생성."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType
from app.core.permissions import HQ_SAFE_WORKSPACE_ROLES
from app.modules.functional_eval.constants import CEO_EVAL_LOGIN_IDS
from app.modules.functional_eval.models import FunctionalEvalViewerProvisionLog
from app.modules.users.hq_safe_accounts import HQ_SAFE_ACCOUNT_SPECS
from app.modules.users.models import User
from app.modules.workers.models import Person, WorkerImportBatch
from app.modules.workers.service import _employee_row_to_dict, _load_sawon_employee_row_dicts

LOGIN_PREFIX = "부현본사-"
SITE_BRACKET_RE = re.compile(r"\[\s*\d*\.[^\]]+\]")

EXCLUDE_JOB_KEYWORDS = ("현장소장", "현장공무")
HQ_INCLUDE_MARKERS = (
    "본사",
    "대표",
    "임원",
    "공사관리",
    "재무회계",
    "외주구매",
    "예산견적",
    "업무팀",
    "안전보건관리실",
    "안전보건실",
    "PM",
)


@dataclass
class ViewerCandidate:
    name: str
    department: str
    position: str
    email: str | None
    birth6: str
    birth_date: date | None
    rrn_hash: str | None
    login_id: str
    person_id: int | None = None


@dataclass
class ViewerProvisionRow:
    name: str
    department: str = ""
    position: str = ""
    email: str | None = None
    login_id: str | None = None
    reason: str = ""
    status: str = "planned"  # planned | excluded | created


@dataclass
class ViewerProvisionResult:
    mode: str
    source_label: str
    planned: list[ViewerProvisionRow] = field(default_factory=list)
    excluded: list[ViewerProvisionRow] = field(default_factory=list)
    created: list[ViewerProvisionRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def row_dict(r: ViewerProvisionRow) -> dict[str, Any]:
            return {
                "name": r.name,
                "department": r.department,
                "position": r.position,
                "email": r.email,
                "login_id": r.login_id,
                "reason": r.reason,
                "status": r.status,
            }

        return {
            "mode": self.mode,
            "source_label": self.source_label,
            "planned_count": len(self.planned),
            "excluded_count": len(self.excluded),
            "created_count": len(self.created),
            "planned": [row_dict(r) for r in self.planned],
            "excluded": [row_dict(r) for r in self.excluded],
            "created": [row_dict(r) for r in self.created],
        }


def _cell_label(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _birth6_from_rrn(rrn_front: Any, rrn_back: Any) -> str | None:
    front = re.sub(r"\D", "", str(rrn_front or "").strip())
    if len(front) >= 6:
        return front[:6]
    back = re.sub(r"\D", "", str(rrn_back or "").strip())
    combined = f"{front}{back}"
    if len(combined) >= 6:
        return combined[:6]
    return None


def _birth_date_from_birth6(birth6: str) -> date | None:
    if len(birth6) != 6 or not birth6.isdigit():
        return None
    yy = int(birth6[:2])
    mm = int(birth6[2:4])
    dd = int(birth6[4:6])
    year = 1900 + yy if yy >= 50 else 2000 + yy
    try:
        return date(year, mm, dd)
    except ValueError:
        return None


def _sawon_values_to_viewer_row(values: list[Any]) -> dict[str, Any] | None:
    base = _employee_row_to_dict(values)
    if not base:
        return None
    vals = list(values)
    while len(vals) < 21:
        vals.append(None)
    department = _cell_label(vals[3])
    position = _cell_label(vals[5])
    email = _cell_label(vals[12]) or _cell_label(vals[11]) or None
    birth6 = _birth6_from_rrn(vals[6], vals[7])
    if not birth6:
        return None
    name = (base.get("name") or "").strip()
    if not name:
        return None
    return {
        **base,
        "name": name,
        "department": department,
        "position": position,
        "email": email or None,
        "birth6": birth6,
        "birth_date": _birth_date_from_birth6(birth6),
    }


def load_viewer_rows_from_path(path: Path) -> tuple[list[dict[str, Any]], str]:
    _row_dicts, _ingestion = _load_sawon_employee_row_dicts(path)
    wb_rows: list[dict[str, Any]] = []
    try:
        from app.modules.workers.service import open_xlrd_workbook

        wb = open_xlrd_workbook(path)
        sh = wb.sheet_by_index(0)
        for r in range(sh.nrows):
            values = [sh.cell_value(r, c) for c in range(sh.ncols)]
            if r == 0:
                h0 = _cell_label(values[0] if values else "")
                compact = h0.replace(" ", "")
                if "성" in h0 and "명" in compact:
                    continue
            row = _sawon_values_to_viewer_row(values)
            if row:
                wb_rows.append(row)
    except Exception:
        wb_rows = []
    if wb_rows:
        return wb_rows, path.name
    raise ValueError("사원리스트에서 부서·직위 라벨을 읽지 못했습니다. xls 형식을 확인하세요.")


def resolve_sawon_source_path(db: Session, explicit: Path | None = None) -> Path | None:
    if explicit is not None and explicit.is_file():
        return explicit
    batch = (
        db.query(WorkerImportBatch)
        .filter(WorkerImportBatch.source_type == "sawon_list_upload")
        .order_by(WorkerImportBatch.created_at.desc())
        .first()
    )
    if batch and batch.stored_path:
        path = Path(batch.stored_path)
        if path.is_file():
            return path
    return None


def _protected_login_ids(db: Session) -> set[str]:
    protected = {spec.login_id for spec in HQ_SAFE_ACCOUNT_SPECS}
    protected |= set(CEO_EVAL_LOGIN_IDS)
    for user in db.query(User).filter(User.is_active.is_(True)).all():
        if user.login_id:
            protected.add(user.login_id.strip())
    return protected


def _protected_names(db: Session) -> set[str]:
    names: set[str] = set()
    for spec in HQ_SAFE_ACCOUNT_SPECS:
        names.add(spec.name.strip())
    for user in db.query(User).filter(User.is_active.is_(True)).all():
        if user.name:
            names.add(user.name.strip())
    return names


def _is_site_assigned(department: str, position: str) -> bool:
    combined = f"{department} {position}"
    if SITE_BRACKET_RE.search(combined):
        return True
    for kw in EXCLUDE_JOB_KEYWORDS:
        if kw in position or kw in department:
            return True
    if "소장" in position and "본사" not in department and "본사" not in position:
        return True
    if position.strip() in {"소장", "현장소장"}:
        return True
    return False


def _is_hq_eligible(department: str, position: str) -> bool:
    if _is_site_assigned(department, position):
        return False
    combined = f"{department} {position}"
    if any(marker in combined for marker in HQ_INCLUDE_MARKERS):
        return True
    if "팀장" in position and "본사" in combined:
        return True
    if "팀원" in position and "본사" in combined:
        return True
    return False


def build_viewer_login_id(name: str) -> str:
    clean = re.sub(r"\s+", "", (name or "").strip())
    return f"{LOGIN_PREFIX}{clean}"


def classify_viewer_candidates(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    protected_logins: set[str] | None = None,
    protected_names: set[str] | None = None,
) -> ViewerProvisionResult:
    protected_logins = protected_logins if protected_logins is not None else _protected_login_ids(db)
    protected_names = protected_names if protected_names is not None else _protected_names(db)
    result = ViewerProvisionResult(mode="dry_run", source_label="")
    seen_names: set[str] = set()
    seen_emails: set[str] = set()

    for row in rows:
        name = (row.get("name") or "").strip()
        department = (row.get("department") or "").strip()
        position = (row.get("position") or "").strip()
        email = (row.get("email") or "").strip() or None
        birth6 = (row.get("birth6") or "").strip()
        login_id = build_viewer_login_id(name)
        base = ViewerProvisionRow(
            name=name,
            department=department,
            position=position,
            email=email,
            login_id=login_id,
        )

        if not name:
            base.reason = "이름 없음"
            result.excluded.append(base)
            continue
        if not birth6 or len(birth6) != 6:
            base.reason = "생년월일 없음"
            result.excluded.append(base)
            continue
        if _is_site_assigned(department, position):
            base.reason = "현장 인원"
            result.excluded.append(base)
            continue
        if not _is_hq_eligible(department, position):
            base.reason = "본사 조회 대상 아님"
            result.excluded.append(base)
            continue
        if name in protected_names:
            base.reason = "이미 계정 존재(이름)"
            result.excluded.append(base)
            continue
        if login_id in protected_logins:
            base.reason = "이미 계정 존재(아이디)"
            result.excluded.append(base)
            continue
        if name in seen_names:
            base.reason = "중복 이름"
            result.excluded.append(base)
            continue
        if email and email.lower() in seen_emails:
            base.reason = "중복 이메일"
            result.excluded.append(base)
            continue

        seen_names.add(name)
        if email:
            seen_emails.add(email.lower())
        result.planned.append(base)

    return result


def dry_run_viewer_accounts(
    db: Session,
    *,
    source_path: Path | None = None,
) -> ViewerProvisionResult:
    path = resolve_sawon_source_path(db, source_path)
    if path is None:
        raise ValueError("사원리스트 파일을 찾을 수 없습니다. HQ에서 사원리스트를 먼저 업로드하세요.")
    rows, label = load_viewer_rows_from_path(path)
    if not rows:
        raise ValueError("사원리스트에서 대상 행을 읽지 못했습니다.")
    result = classify_viewer_candidates(db, rows)
    result.mode = "dry_run"
    result.source_label = label
    log = FunctionalEvalViewerProvisionLog(
        mode="dry_run",
        source_label=label,
        planned_count=len(result.planned),
        excluded_count=len(result.excluded),
        applied_count=0,
        result_json=json.dumps(result.to_dict(), ensure_ascii=False),
    )
    db.add(log)
    db.commit()
    return result


def apply_viewer_accounts(
    db: Session,
    *,
    source_path: Path | None = None,
    actor: User | None = None,
) -> ViewerProvisionResult:
    path = resolve_sawon_source_path(db, source_path)
    if path is None:
        raise ValueError("사원리스트 파일을 찾을 수 없습니다.")
    rows, label = load_viewer_rows_from_path(path)
    if not rows:
        raise ValueError("사원리스트에서 대상 행을 읽지 못했습니다.")
    result = classify_viewer_candidates(db, rows)
    result.mode = "apply"
    result.source_label = label
    now = utc_now()

    row_by_name = {(r.get("name") or "").strip(): r for r in rows}
    for planned in result.planned:
        src = row_by_name.get(planned.name)
        if not src:
            planned.status = "excluded"
            planned.reason = "원본 행 없음"
            result.excluded.append(planned)
            continue
        birth6 = (src.get("birth6") or "").strip()
        login_id = build_viewer_login_id(planned.name)
        if db.query(User).filter(User.login_id == login_id).first():
            planned.status = "excluded"
            planned.reason = "이미 계정 존재"
            result.excluded.append(planned)
            continue

        person_id = None
        rrn_hash = src.get("rrn_hash")
        if rrn_hash:
            person = db.query(Person).filter(Person.rrn_hash == rrn_hash).first()
            if person:
                person_id = person.id
                if src.get("email"):
                    person.email = src["email"]

        user = User(
            name=planned.name,
            login_id=login_id,
            password_hash=get_password_hash(birth6),
            birth_date=src.get("birth_date"),
            department=planned.department or None,
            role=Role.FUNCTIONAL_EVAL_VIEWER,
            ui_type=UIType.HQ_SAFE,
            person_id=person_id,
            is_active=True,
            must_change_password=True,
            initial_password_issued=True,
            account_issued_by="hq_viewer_bulk",
            account_issued_at=now,
        )
        db.add(user)
        planned.status = "created"
        result.created.append(planned)

    log = FunctionalEvalViewerProvisionLog(
        mode="apply",
        source_label=label,
        created_by_user_id=actor.id if actor else None,
        created_by_login_id=(actor.login_id if actor else None),
        planned_count=len(result.planned),
        excluded_count=len(result.excluded),
        applied_count=len(result.created),
        result_json=json.dumps(result.to_dict(), ensure_ascii=False),
    )
    db.add(log)
    db.commit()
    return result


def list_viewer_provision_logs(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        db.query(FunctionalEvalViewerProvisionLog)
        .order_by(FunctionalEvalViewerProvisionLog.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row.result_json) if row.result_json else {}
        out.append(
            {
                "id": row.id,
                "created_at": row.created_at.isoformat(),
                "mode": row.mode,
                "source_label": row.source_label,
                "planned_count": row.planned_count,
                "excluded_count": row.excluded_count,
                "applied_count": row.applied_count,
                "created_by_login_id": row.created_by_login_id,
                "summary": payload,
            }
        )
    return out
