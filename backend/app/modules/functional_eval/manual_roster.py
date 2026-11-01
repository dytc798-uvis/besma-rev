"""Manual XLSX review and additive import; never a full-roster replacement."""
from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
import threading
import time
import uuid
import zipfile
from pathlib import Path

import openpyxl
from sqlalchemy import text

from app.modules.functional_eval.models import (
    FunctionalEvalAssessment, FunctionalEvalPeriod, FunctionalEvalRosterImportBatch,
    FunctionalEvalSignature, FunctionalEvalSiteApproval, FunctionalEvalSiteRegistry,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.roster import ParsedRosterRow, hash_rrn, mask_rrn, normalize_job_code, normalize_site_code
from app.modules.functional_eval import additional_rounds
from app.modules.functional_eval.models import FunctionalEvalAdditionalApproval,FunctionalEvalTargetEnrollment,FunctionalEvalPeriodMode,FunctionalEvalIntakeReceipt

MAX_BYTES = 20 * 1024 * 1024
_tickets: dict[str, dict] = {}
_ticket_lock = threading.Lock()


class ReviewRequired(ValueError):
    pass


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()


def _period(db, period_id: int):
    from app.modules.functional_eval.service import assert_period_editable
    period = db.query(FunctionalEvalPeriod).filter_by(is_active=True).order_by(FunctionalEvalPeriod.id.desc()).first()
    if period is None or period.id != period_id:
        raise ReviewRequired('현재 평가기간을 다시 확인해 주세요.')
    try:
        assert_period_editable(period)
    except ValueError as error:
        raise ReviewRequired('마감된 평가기간에는 자료를 반영할 수 없습니다.') from error
    return period


def parse_file(raw: bytes, filename: str) -> list[ParsedRosterRow]:
    if Path(filename).suffix.lower() != '.xlsx':
        raise ReviewRequired('일용직 참조명부는 xlsx 파일을 선택해 주세요. 출역일보는 별도 자료입니다.')
    if not raw or len(raw) > MAX_BYTES:
        raise ReviewRequired('비어 있지 않은 20MB 이하 xlsx 파일을 선택해 주세요.')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.infolist()) > 10000 or sum(x.file_size for x in archive.infolist()) > MAX_BYTES:
                raise ReviewRequired('압축 해제 크기가 20MB 이하인 xlsx 파일을 선택해 주세요.')
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        try:
            found, seen = [], set()
            for sheet in workbook.worksheets:
                rows = sheet.iter_rows(values_only=True)
                headers = [str(x or '').strip() for x in next(rows, ())]
                if not any(headers):
                    if any(any(x is not None and str(x).strip() for x in row) for row in rows):
                        raise ReviewRequired(f'‘{sheet.title}’ 시트의 첫 행에 명부 머리글을 넣어 주세요. 자료를 반영하지 않았습니다.')
                    continue
                def column(predicate, required=True):
                    matches = [i for i, header in enumerate(headers) if predicate(header)]
                    if len(matches) != 1 and required:
                        raise ReviewRequired(f'‘{sheet.title}’ 시트의 성명·주민번호·소속현장 또는 현장코드 머리글을 확인해 주세요. 자료를 반영하지 않았습니다.')
                    return matches[0] if len(matches) == 1 else None
                name_i = column(lambda x: '성' in x and '명' in x)
                rrn_i = column(lambda x: '주민' in x)
                site_i = column(lambda x: '소속현장' in x or '현장코드' in x)
                job_i = column(lambda x: '직종' in x, False)
                phone_i = column(lambda x: '휴대' in x or '핸드' in x, False)
                for number, row in enumerate(rows, 2):
                    if not any(x is not None and str(x).strip() for x in row):
                        continue
                    def cell(index):
                        return str(row[index]).strip() if index is not None and index < len(row) and row[index] is not None else ''
                    name, site = cell(name_i), normalize_site_code(cell(site_i))
                    digits = re.sub(r'\D', '', cell(rrn_i))
                    if not name or len(name) > 100 or not site or len(site) > 50 or len(digits) != 13:
                        raise ReviewRequired(f'‘{sheet.title}’ 시트 {number}행의 성명·식별정보·현장코드를 확인해 주세요. 자료를 반영하지 않았습니다.')
                    key = hash_rrn(digits)
                    if key in seen:
                        raise ReviewRequired(f'‘{sheet.title}’ 시트 {number}행에 중복 식별정보가 있습니다. 다른 시트도 함께 확인한 뒤 다시 선택해 주세요.')
                    seen.add(key)
                    job = normalize_job_code(cell(job_i))
                    found.append(ParsedRosterRow(name, site, digits, key, mask_rrn(digits), job, job == '1', cell(phone_i) or None))
            if not found:
                raise ReviewRequired('확인할 근로자 행이 없습니다. 자료 종류와 범위를 확인해 주세요.')
            return found
        finally:
            workbook.close()
    except ReviewRequired:
        raise
    except Exception as error:
        raise ReviewRequired('xlsx 구조를 읽을 수 없습니다. 원본 형식을 확인해 주세요.') from error


def _state(db, period):
    workers = db.query(FunctionalEvalWorker).filter_by(period_id=period.id).order_by(FunctionalEvalWorker.id).all()
    registry = db.query(FunctionalEvalSiteRegistry).order_by(FunctionalEvalSiteRegistry.id).all()
    assessments = db.query(FunctionalEvalAssessment).join(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id == period.id).order_by(FunctionalEvalAssessment.id).all()
    signatures = db.query(FunctionalEvalSignature).filter_by(period_id=period.id).order_by(FunctionalEvalSignature.id).all()
    approvals = db.query(FunctionalEvalSiteApproval).filter_by(period_id=period.id).order_by(FunctionalEvalSiteApproval.id).all()
    extra=[]
    if additional_rounds.schema_ready(db):
        for model in [FunctionalEvalAdditionalApproval,FunctionalEvalTargetEnrollment,FunctionalEvalPeriodMode]:extra.append(db.query(model).filter_by(period_id=period.id).all())
    # Hash the reviewed state, including changes to existing evaluation/signature scopes.
    values = lambda rows: [{c.name: getattr(x, c.name) for c in x.__table__.columns} for x in rows]
    fingerprint = _digest([{'id': period.id, 'title': period.title, 'deadline': period.deadline_date, 'active': period.is_active},
                           values(workers), values(registry), values(assessments), values(signatures), values(approvals),*[values(rows)for rows in extra]])
    protected = {x.worker_id for x in assessments}
    protected_sites = {x.site_code for x in signatures if x.site_code}
    protected_sites.update(x.site_code for x in approvals if x.evaluation_completed_at or x.site_submitted_at or x.status not in {'IN_PROGRESS', 'REJECTED'})
    return workers, {x.site_code: x for x in registry}, protected, protected_sites, fingerprint


def _plan(db, period, rows):
    workers, sites, protected, protected_sites, fingerprint = _state(db, period)
    existing = {x.rrn_hash: x for x in workers}
    actions = []
    for row in rows:
        old = existing.get(row.rrn_hash)
        fields_changed = old is not None and (old.name != row.name or row.job_code is not None and old.job_code != row.job_code or row.phone is not None and old.phone_mobile != row.phone)
        if row.site_code not in sites:
            action, reason = 'CHECK_REQUIRED', '확인된 현장코드와 연결되지 않습니다.'
        elif old and old.site_code != row.site_code:
            action, reason = 'CHECK_REQUIRED', '기존 소속현장이 달라 개별 확인이 필요합니다.'
        elif old and row.job_code is not None and old.is_site_manager != row.is_site_manager:
            action, reason = 'CHECK_REQUIRED', '소장·근로자 구분 변경은 개별 확인이 필요합니다.'
        elif old and (old.id in protected or old.site_code in protected_sites or not old.is_active) and fields_changed:
            action, reason = 'PRESERVED', '기존 평가·서명·결재 또는 제외 이력이 있어 정보를 유지합니다.'
        elif old is None:
            action, reason = 'NEW', '참조명부에 추가합니다. 계정과 출역은 생성하지 않습니다.'
        elif fields_changed:
            action, reason = 'UPDATED', '성명·직종·연락처만 갱신합니다.'
        else:
            action, reason = 'UNCHANGED', '기존 정보를 유지합니다.'
        actions.append((row, old, action, reason))
    received_hashes = {row.rrn_hash for row in rows}
    missing = sum(worker.rrn_hash not in received_hashes for worker in workers)
    counts = {key: sum(x[2] == key for x in actions) for key in ['NEW', 'UPDATED', 'UNCHANGED', 'PRESERVED', 'CHECK_REQUIRED']}
    return actions, sites, fingerprint, missing, counts



def _review_item(row, old, action, reason):
    # Only fields which the existing planner will update are described.
    # Raw identity and phone values never enter the preview response.
    changes = []
    if action == 'UPDATED' and old is not None:
        if old.name != row.name:
            changes.append({'label': '성명', 'before': old.name or '', 'after': row.name})
        if row.job_code is not None and old.job_code != row.job_code:
            changes.append({'label': '직종', 'before': old.job_code or '미입력', 'after': row.job_code})
        if row.phone is not None and old.phone_mobile != row.phone:
            changes.append({'label': '연락처', 'before': None, 'after': None})
    return {'name': row.name, 'site_code': row.site_code, 'action': action, 'reason': reason, 'changes': changes}


def preview(db, actor_id: int, period_id: int, raw: bytes, filename: str):
    period = _period(db, period_id)
    rows = parse_file(raw, filename)
    actions, sites, fingerprint, missing, counts = _plan(db, period, rows)
    token = secrets.token_urlsafe(24);review_id=uuid.uuid4().hex
    now = time.monotonic()
    with _ticket_lock:
        for key in list(_tickets):
            if _tickets[key]['expires'] <= now:
                del _tickets[key]
        if len(_tickets) >= 256:
            raise ReviewRequired('자료 확인 요청이 많습니다. 잠시 후 다시 확인해 주세요.')
        _tickets[token] = dict(actor=actor_id, period=period.id, filename=Path(filename).name,review_id=review_id,
                               sha=hashlib.sha256(raw).hexdigest(), state=fingerprint, expires=now + 900)
    target_review,_=additional_rounds.enrollment_review(db,period_id,actions,sites)
    return {'preview_token': token,'review_id':review_id,'target_review':target_review, 'source_sha256': hashlib.sha256(raw).hexdigest(), 'filename': Path(filename).name,
            'period': {'id': period.id, 'title': period.title, 'deadline_date': period.deadline_date},
            'material_kind': 'REFERENCE_ROSTER', 'coverage_status': 'UNKNOWN_UPSERT_ONLY', 'parsed_rows': len(rows),
            'counts': counts, 'retained_missing': missing, 'can_apply': counts['CHECK_REQUIRED'] == 0,
            'sites': [{'site_code': code, 'site_name': sites[code].erp_site_label if code in sites else None,
                       'confirmed': code in sites} for code in sorted({r.site_code for r in rows})],
            'items': [_review_item(row, old, action, reason) for row, old, action, reason in actions]}


def apply(db, actor_id: int, period_id: int, token: str, raw: bytes, filename: str, archive_root: Path, *, add_to_targets=False,review_id=None):
    # Serialize SQLite writers while comparing reviewed state and applying its additions.
    db.rollback()
    db.execute(text('BEGIN IMMEDIATE'))
    try:
        source_sha=hashlib.sha256(raw).hexdigest();confirmation_sha=hashlib.sha256(token.encode()).hexdigest()
        if additional_rounds.schema_ready(db):
            previous=db.query(FunctionalEvalIntakeReceipt).filter_by(confirmation_sha256=confirmation_sha).first()
            if previous:
                if previous.actor_id!=actor_id or previous.period_id!=period_id or previous.source_sha256!=source_sha or previous.filename!=Path(filename).name or bool(previous.result_json.get('targets_requested'))!=add_to_targets or review_id is not None and review_id!=previous.id:raise ReviewRequired('확인한 자료의 반영 범위가 다릅니다.')
                result=dict(previous.result_json);db.rollback();return result
        period = _period(db, period_id)
        rows = parse_file(raw, filename)
        actions, sites, fingerprint, missing, counts = _plan(db, period, rows)
        target_review,candidates=additional_rounds.enrollment_review(db,period_id,actions,sites)
        if add_to_targets and not target_review['can_add']:raise ReviewRequired('추가 평가 대상과 담당 계정을 다시 확인해 주세요.')
        with _ticket_lock:
            ticket = _tickets.get(token)
            if not ticket or ticket['expires'] <= time.monotonic() or ticket['actor'] != actor_id or ticket['period'] != period_id or ticket['filename'] != Path(filename).name or ticket['sha'] != hashlib.sha256(raw).hexdigest() or ticket['state'] != fingerprint:
                raise ReviewRequired('미리보기 확인이 만료됐거나 파일·평가기간·계정·기존 자료가 달라졌습니다. 차이를 다시 확인해 주세요.')
            if counts['CHECK_REQUIRED']:
                raise ReviewRequired('연결되지 않거나 변경된 현장을 먼저 확인해 주세요.')
            if review_id is not None and review_id!=ticket['review_id']:raise ReviewRequired('확인한 자료의 반영 범위가 다릅니다.')
            receipt_id=ticket['review_id']
            del _tickets[token]  # One application attempt; never replay a saved confirmation.
        archive_root.mkdir(parents=True, exist_ok=True)
        saved = archive_root / ('manual_roster_' + uuid.uuid4().hex + '.xlsx')
        with saved.open('xb') as stream:
            stream.write(raw)
        row_numbers = {};created={}
        for row, old, action, _ in actions:
            if action == 'NEW':
                if row.site_code not in row_numbers:
                    row_numbers[row.site_code] = max((x.row_no for x in db.query(FunctionalEvalWorker).filter_by(period_id=period_id, site_code=row.site_code)), default=0)
                row_numbers[row.site_code] += 1
                worker=FunctionalEvalWorker(period_id=period_id, site_code=row.site_code, site_name=sites[row.site_code].erp_site_label[:300],
                    row_no=row_numbers[row.site_code], name=row.name, rrn_hash=row.rrn_hash, rrn_masked=row.rrn_masked, job_code=row.job_code,
                    phone_mobile=row.phone, is_site_manager=row.is_site_manager, is_active=True, is_on_reference_roster=True)
                db.add(worker);created[row.rrn_hash]=worker
            elif action == 'UPDATED':
                old.name = row.name
                if row.job_code is not None:
                    old.job_code = row.job_code
                if row.phone is not None:
                    old.phone_mobile = row.phone
        batch = FunctionalEvalRosterImportBatch(period_id=period_id, original_filename=Path(filename).name[:255], stored_path=str(saved),
            total_rows=len(rows), new_count=counts['NEW'], updated_count=counts['UPDATED'],
            unchanged_count=counts['UNCHANGED'] + counts['PRESERVED'], removed_count=0)
        db.add(batch);db.flush()
        enrolled=additional_rounds.enroll(db,period_id,actor_id,source_sha,batch.id,candidates,created)if add_to_targets else[]
        result={'batch_id': batch.id, 'period_id': period_id, 'source_sha256': source_sha,'review_id':receipt_id,
                'coverage_status': 'UNKNOWN_UPSERT_ONLY', 'counts': counts, 'retained_missing': missing,
                'deactivated': 0, 'evaluations_signatures_approvals_preserved': True,'targets_requested':add_to_targets,
                'targets_added':len(enrolled),'evaluation_targets':enrolled,'attendance_created':0}
        if additional_rounds.schema_ready(db):db.add(FunctionalEvalIntakeReceipt(id=receipt_id,confirmation_sha256=confirmation_sha,actor_id=actor_id,period_id=period_id,roster_batch_id=batch.id,source_sha256=source_sha,filename=Path(filename).name,result_json=result))
        db.commit()
        return result
    except BaseException:
        db.rollback()
        raise


def receipt(db,actor_id,period_id,review_id,source_sha):
    if not additional_rounds.schema_ready(db):raise ReviewRequired('반영 결과 확인 기능을 준비하고 있습니다.')
    record=db.get(FunctionalEvalIntakeReceipt,review_id)
    if record is None or record.actor_id!=actor_id or record.period_id!=period_id or record.source_sha256!=source_sha:raise KeyError('RECEIPT_NOT_FOUND')
    return dict(record.result_json)
