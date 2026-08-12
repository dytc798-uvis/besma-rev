import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSiteRegistry, FunctionalEvalWorker
from app.modules.sites.models import Site
from app.modules.worker_feedback.models import WorkerFeedbackOpinion


router = APIRouter(prefix="/worker-feedback", tags=["worker-feedback"])

_READ_ROLES = {
    Role.HQ_SAFE.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.SUPER_ADMIN.value,
    Role.ACCIDENT_ADMIN.value,
    Role.FUNCTIONAL_EVAL_VIEWER.value,
    Role.SITE.value,
}
_HQ_ROLES = {
    Role.HQ_SAFE.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.SUPER_ADMIN.value,
    Role.ACCIDENT_ADMIN.value,
    Role.FUNCTIONAL_EVAL_VIEWER.value,
}

_KEY_TIMESTAMP = "타임스탬프"
_KEY_NAME = "1. 귀하의 성함을 입력하십시오."
_KEY_BIRTH = "2. 귀하의 생년월일 6자리를 입력하십시오."
_KEY_PHONE = "3. 귀하의 휴대전화 번호를 입력하십시오."
_KEY_TYPE = "4. 의견 종류"
_KEY_CONTENT = "5. 의견"
_KEY_SITE = "현장명"


def _role_value(role: Role | str | None) -> str | None:
    return role.value if isinstance(role, Role) else (str(role) if role is not None else None)


def _assert_can_read(current_user: Any) -> None:
    if _role_value(getattr(current_user, "role", None)) not in _READ_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed")


def _is_hq_user(current_user: Any) -> bool:
    return _role_value(getattr(current_user, "role", None)) in _HQ_ROLES


def _assert_site_user(current_user: Any) -> None:
    if _role_value(getattr(current_user, "role", None)) != Role.SITE.value:
        raise HTTPException(status_code=403, detail="현장 계정만 접수와 조치를 기록할 수 있습니다.")


def _site_code_for_user(db: DbDep, current_user: Any) -> str | None:
    site_id = getattr(current_user, "site_id", None)
    site = db.query(Site).filter(Site.id == site_id).first() if site_id else None
    return site.site_code if site else None


def _build_script_url(limit: int = 1000) -> str:
    raw_url = (settings.google_worker_feedback_webapp_url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=503, detail="Google worker feedback web app URL is not configured")
    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    secret = (settings.google_worker_feedback_secret or "").strip()
    if secret and "token" not in query:
        query["token"] = secret
    query["limit"] = str(limit)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _fetch_script_rows(limit: int) -> list[dict[str, Any]]:
    request = Request(_build_script_url(limit), headers={"Accept": "application/json", "User-Agent": "BESMA/worker-feedback"})
    try:
        with urlopen(request, timeout=settings.google_worker_feedback_timeout_seconds) as response:
            payload = response.read().decode(response.headers.get_content_charset() or "utf-8")
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Google worker feedback endpoint returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail="Google worker feedback endpoint is not reachable") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Google worker feedback endpoint did not return valid JSON") from exc
    rows = data.get("data") if isinstance(data, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _row_value(row: dict[str, Any], exact_key: str, fallback_terms: list[str]) -> str:
    if exact_key in row:
        value = row.get(exact_key)
        return "" if value is None else str(value).strip()
    for key, value in row.items():
        if any(term.lower() in str(key).lower() for term in fallback_terms):
            return "" if value is None else str(value).strip()
    return ""


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    return "0" + digits[2:] if digits.startswith("82") and len(digits) >= 11 else digits


def _mask_phone(value: str) -> str:
    digits = _normalize_phone(value)
    return f"{digits[:3]}-****-{digits[-4:]}" if len(digits) >= 7 else ("****" if digits else "")


def _parse_submitted_at(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y. %m. %d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _active_period(db: DbDep) -> FunctionalEvalPeriod | None:
    return db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.is_active == True).order_by(FunctionalEvalPeriod.id.desc()).first()  # noqa: E712


def _active_workers(db: DbDep) -> list[FunctionalEvalWorker]:
    period = _active_period(db)
    if period is None:
        return []
    return db.query(FunctionalEvalWorker).filter(
        FunctionalEvalWorker.period_id == period.id,
        FunctionalEvalWorker.is_active == True,  # noqa: E712
    ).all()


def _site_names(db: DbDep) -> dict[str, str]:
    result = {row.site_code: (row.erp_site_label or row.site_code) for row in db.query(FunctionalEvalSiteRegistry).all()}
    for row in db.query(Site).all():
        if row.site_code:
            result.setdefault(row.site_code, row.site_name or row.site_code)
    return result


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def _match_identity(db: DbDep, phone: str, site_hint: str, worker_name: str) -> dict[str, Any]:
    normalized_phone = _normalize_phone(phone)
    workers = _active_workers(db)
    phone_matches = [w for w in workers if normalized_phone and _normalize_phone(w.phone_mobile or "") == normalized_phone]
    names = _site_names(db)
    candidate_workers = phone_matches
    if len({w.site_code for w in candidate_workers}) > 1 and site_hint:
        hint = _norm_text(site_hint)
        filtered = [w for w in candidate_workers if hint in _norm_text(names.get(w.site_code, w.site_name or w.site_code))]
        if filtered:
            candidate_workers = filtered
    site_codes = sorted({w.site_code for w in candidate_workers if w.site_code})
    if not site_codes and site_hint:
        hint = _norm_text(site_hint)
        site_codes = [code for code, name in names.items() if hint and (hint in _norm_text(name) or _norm_text(name) in hint)]
    if len(site_codes) != 1:
        return {"match_status": "ambiguous" if len(site_codes) > 1 else "unmatched", "site_code": None, "site_name": None, "worker_id": None}
    site_code = site_codes[0]
    same_site_workers = [w for w in candidate_workers if w.site_code == site_code]
    if len(same_site_workers) > 1 and worker_name:
        exact_name = [w for w in same_site_workers if _norm_text(w.name) == _norm_text(worker_name)]
        if exact_name:
            same_site_workers = exact_name
    worker_id = same_site_workers[0].id if len(same_site_workers) == 1 else None
    return {"match_status": "matched", "site_code": site_code, "site_name": names.get(site_code, site_code), "worker_id": worker_id}


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("\n".join((part or "").strip() for part in parts).encode("utf-8")).hexdigest()


def _opinion_from_raw(db: DbDep, row: dict[str, Any]) -> dict[str, Any]:
    submitted_raw = _row_value(row, _KEY_TIMESTAMP, ["timestamp"])
    name = _row_value(row, _KEY_NAME, ["성함", "성명", "이름", "name"])
    birth6 = _row_value(row, _KEY_BIRTH, ["생년월일", "birth"])
    phone = _row_value(row, _KEY_PHONE, ["휴대전화", "휴대폰", "전화", "phone"])
    opinion_type = _row_value(row, _KEY_TYPE, ["의견 종류", "종류", "type"])
    content = _row_value(row, _KEY_CONTENT, ["의견 내용", "content"])
    site_hint = _row_value(row, _KEY_SITE, ["현장명", "근무현장", "소속현장", "site"])
    match = _match_identity(db, phone, site_hint, name)
    return {
        "source_fingerprint": _fingerprint(submitted_raw, _normalize_phone(phone), opinion_type, content),
        "submitted_at": _parse_submitted_at(submitted_raw),
        "submitted_at_raw": submitted_raw,
        "worker_name": name,
        "birth6": birth6,
        "phone_normalized": _normalize_phone(phone),
        "phone_masked": _mask_phone(phone),
        "opinion_type": opinion_type,
        "content": content,
        "submitted_site_name": site_hint or None,
        "matched_site_code": match["site_code"],
        "matched_site_name": match["site_name"],
        "matched_worker_id": match["worker_id"],
        "match_status": match["match_status"],
        "raw_json": json.dumps(row, ensure_ascii=False),
    }


def _sync_from_google(db: DbDep, limit: int = 1000) -> dict[str, Any]:
    rows = _fetch_script_rows(limit)
    created = updated = 0
    for raw in rows:
        payload = _opinion_from_raw(db, raw)
        existing = db.query(WorkerFeedbackOpinion).filter(WorkerFeedbackOpinion.source_fingerprint == payload["source_fingerprint"]).first()
        if existing is None:
            db.add(WorkerFeedbackOpinion(**payload))
            created += 1
        else:
            for key, value in payload.items():
                if key != "source_fingerprint":
                    setattr(existing, key, value)
            updated += 1
    db.commit()
    return {"fetched": len(rows), "created": created, "updated": updated, "error": None}


def _serialize(row: WorkerFeedbackOpinion) -> dict[str, Any]:
    return {
        "id": row.id,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "submitted_at_raw": row.submitted_at_raw,
        "worker_name": row.worker_name,
        "phone_masked": row.phone_masked,
        "opinion_type": row.opinion_type,
        "content": row.content,
        "submitted_site_name": row.submitted_site_name,
        "matched_site_code": row.matched_site_code,
        "matched_site_name": row.matched_site_name,
        "matched_worker_id": row.matched_worker_id,
        "match_status": row.match_status,
        "action_status": row.action_status,
        "site_received_at": row.site_received_at.isoformat() if row.site_received_at else None,
        "action_taken_at": row.action_taken_at.isoformat() if row.action_taken_at else None,
        "action_result": row.action_result,
        "appropriateness_score": row.appropriateness_score,
        "actionability_score": row.actionability_score,
        "prevention_score": row.prevention_score,
        "score_total": row.score_total,
        "bonus_points": row.bonus_points,
        "bonus_awarded_at": row.bonus_awarded_at.isoformat() if row.bonus_awarded_at else None,
        "route": row.route,
        "notes": row.notes,
    }


def _query_for_user(db: DbDep, current_user: Any):
    query = db.query(WorkerFeedbackOpinion)
    if not _is_hq_user(current_user):
        site_code = _site_code_for_user(db, current_user)
        if not site_code:
            raise HTTPException(status_code=403, detail="Site context is required")
        query = query.filter(WorkerFeedbackOpinion.matched_site_code == site_code)
    return query


def _visible_opinion(db: DbDep, current_user: Any, opinion_id: int) -> WorkerFeedbackOpinion:
    row = _query_for_user(db, current_user).filter(WorkerFeedbackOpinion.id == opinion_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Worker feedback opinion not found")
    return row


@router.post("/sync")
def sync_worker_feedback(db: DbDep, current_user: CurrentUserDep):
    if not _is_hq_user(current_user):
        raise HTTPException(status_code=403, detail="Not allowed")
    return _sync_from_google(db)


@router.get("/responses")
def list_worker_feedback_responses(db: DbDep, current_user: CurrentUserDep, limit: int = Query(default=500, ge=1, le=1000)):
    _assert_can_read(current_user)
    sync_result: dict[str, Any] | None = None
    try:
        sync_result = _sync_from_google(db, limit=1000)
    except HTTPException as exc:
        sync_result = {"error": exc.detail}
    rows = _query_for_user(db, current_user).order_by(WorkerFeedbackOpinion.submitted_at.desc().nullslast(), WorkerFeedbackOpinion.id.desc()).limit(limit).all()
    return {"count": len(rows), "items": [_serialize(row) for row in rows], "sync": sync_result}


@router.get("/menu-status")
def worker_feedback_menu_status(db: DbDep, current_user: CurrentUserDep):
    _assert_can_read(current_user)
    pending_count = _query_for_user(db, current_user).filter(WorkerFeedbackOpinion.action_status != "DONE").count()
    return {"pending_count": pending_count}


@router.post("/{opinion_id}/receive")
def receive_worker_feedback_opinion(opinion_id: int, db: DbDep, current_user: CurrentUserDep):
    _assert_site_user(current_user)
    row = _visible_opinion(db, current_user, opinion_id)
    if row.action_status == "PENDING":
        row.action_status = "RECEIVED"
        row.site_received_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(row)
    return _serialize(row)


@router.post("/{opinion_id}/complete")
def complete_worker_feedback_opinion(opinion_id: int, db: DbDep, current_user: CurrentUserDep, action_result: str = Body(default="", embed=True)):
    _assert_site_user(current_user)
    row = _visible_opinion(db, current_user, opinion_id)
    if not action_result.strip():
        raise HTTPException(status_code=400, detail="조치 결과를 입력해야 합니다.")
    row.action_status = "DONE"
    row.action_taken_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.response_at = row.action_taken_at
    row.action_result = action_result.strip()
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.patch("/{opinion_id}/score")
def score_worker_feedback_opinion(
    opinion_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    appropriateness_score: int = Body(..., ge=1, le=5),
    actionability_score: int = Body(..., ge=1, le=5),
    prevention_score: int = Body(..., ge=1, le=5),
    notes: str = Body(default=""),
):
    if not _is_hq_user(current_user):
        raise HTTPException(status_code=403, detail="Not allowed")
    row = _visible_opinion(db, current_user, opinion_id)
    if row.action_status != "DONE":
        raise HTTPException(status_code=409, detail="현장 조치완료 후 본사에서 평가할 수 있습니다.")
    row.appropriateness_score = appropriateness_score
    row.actionability_score = actionability_score
    row.prevention_score = prevention_score
    row.score_total = appropriateness_score + actionability_score + prevention_score
    row.notes = notes.strip() or row.notes
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/{opinion_id}/award")
def award_worker_feedback_bonus(
    opinion_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    bonus_points: int = Body(default=5, ge=1, le=100, embed=True),
):
    if not _is_hq_user(current_user):
        raise HTTPException(status_code=403, detail="Not allowed")
    row = _visible_opinion(db, current_user, opinion_id)
    if row.action_status != "DONE" or row.score_total is None:
        raise HTTPException(status_code=409, detail="현장 조치와 본사 평가를 먼저 완료해야 합니다.")
    if not row.matched_worker_id:
        raise HTTPException(status_code=409, detail="전화번호로 기능인을 특정하지 못해 가점을 줄 수 없습니다.")
    if row.bonus_awarded_at is not None:
        raise HTTPException(status_code=409, detail="이미 가점이 확정된 의견입니다.")
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == row.matched_worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="기능인 정보를 찾을 수 없습니다.")
    row.bonus_points = bonus_points
    row.bonus_awarded_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.bonus_awarded_by_user_id = current_user.id
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("/status")
def get_worker_feedback_status(current_user: CurrentUserDep):
    _assert_can_read(current_user)
    return {
        "configured": bool((settings.google_worker_feedback_webapp_url or "").strip()),
        "has_secret": bool((settings.google_worker_feedback_secret or "").strip()),
        "deployment_id_configured": bool((settings.google_worker_feedback_deployment_id or "").strip()),
    }
