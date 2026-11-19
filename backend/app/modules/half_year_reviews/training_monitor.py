"""Emergency training matrix. Existing evaluations and historical ledgers stay intact."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import base64, copy, hashlib, io, json, sqlite3

PERIODS = ('2025-H1', '2025-H2', '2026-H1', '2026-H2')
PERIOD_LABELS = ('2025 상반기', '2025 하반기', '2026 상반기', '2026 하반기')
STATES = {'실시', '미실시', '미확인', '재확인', '적합', '보완', '—'}


def relevant(data):
    record = data.get('assessments', {}).get('report:site', {})
    answers = {kind: (record.get(kind) or {}).get('data', {}).get('answers', {}).get('p13')
               for kind in ('draft', 'completed')}
    evidence = data.get('evidence', {}).get('emergency_drill') or {}
    return {'answers': answers,
            'evidence': {k: evidence.get(k) for k in ('checked', 'hold', 'note')},
            'files': sorted((f['id'], f.get('sha256')) for f in data.get('files', [])
                            if f.get('evidence_id') == 'emergency_drill')}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def evaluation(data):
    current = relevant(data)
    complete = current['answers']['completed']
    draft = current['answers']['draft']
    if complete and draft != complete:
        return '재확인', '비상훈련 평가내용이 완료 저장본과 다릅니다.'
    if not complete or complete.get('value') is None:
        return None, None
    value = complete['value']
    if value == 'EXCELLENT' or type(value) in (int, float) and value == 7:
        return '적합', '현재 반기평가 비상훈련 항목: 만점.'
    if value in ('NORMAL', 'POOR') or type(value) in (int, float) and 0 <= value < 7:
        return '보완', '현재 반기평가 비상훈련 항목: 보완이 필요한 평가.'
    return '재확인', '비상훈련 평가값을 확인해야 합니다.'


def matrix(seed, states, visible_ids, full_scope, current_sites=None):
    if seed.get('schema') != 1 or seed.get('periods') != list(PERIODS):
        raise ValueError('TRAINING_HISTORY_INVALID')
    sites = copy.deepcopy(seed['sites'])
    if len({s['id'] for s in sites}) != len(sites):
        raise ValueError('TRAINING_SITE_DUPLICATE')
    records = {}
    for record in seed['records']:
        key = record['site_id'] + '|' + record['period']
        if key in records or record['period'] not in PERIODS:
            raise ValueError('TRAINING_RECORD_DUPLICATE')
        records[key] = record
    by_id = {s['id']: s for s in sites}
    for site in current_sites or []:
        if site['id'] not in by_id:
            sites.append(site.copy());by_id[site['id']] = sites[-1]
        else:
            by_id[site['id']].update(site)
        key=site['id']+'|2026-H2'
        records.setdefault(key,{'conducted':'미확인','suitability':'미확인','reasons':[],'sources':[]})
    items = []
    for site in sites:
        if not full_scope and site['public_id'] not in visible_ids:
            continue
        cells = {}
        for period in PERIODS:
            key = site['id'] + '|' + period
            historical = records.get(key)
            data = states.get(key)
            if not historical and not data:
                cells[period] = {'conducted': '—', 'suitability': '—', 'reasons': [], 'sources': []}
                continue
            cell = copy.deepcopy(historical or {'conducted': '미확인', 'suitability': '미확인', 'reasons': [], 'sources': []})
            cell = {k: cell[k] for k in ('conducted', 'suitability', 'reasons', 'sources')}
            if data:
                grade, explanation = evaluation(data)
                if grade:
                    cell['reasons'].append(explanation)
                    cell['sources'].append('BESMA 반기평가 · 비상사태훈련보고서 및 교육일지')
                    if not historical or not historical.get('live_bound'):
                        cell['suitability'] = grade
                expected = seed.get('live_fingerprints', {}).get(key)
                if expected and expected != fingerprint(relevant(data)):
                    cell.update(conducted='재확인', suitability='재확인')
                    cell['reasons'].append('훈련자료 또는 평가가 변경됐습니다. 기존 판단을 다시 확인해 주세요.')
                # Neither an attachment nor a positive score establishes the actual exercise date.
                if relevant(data)['answers']['draft'] != relevant(data)['answers']['completed'] and relevant(data)['answers']['completed']:
                    cell['suitability'] = '재확인'
            if cell['conducted'] not in STATES or cell['suitability'] not in STATES:
                raise ValueError('TRAINING_STATE_INVALID')
            cell['reasons'] = list(dict.fromkeys(cell['reasons']))
            cell['sources'] = list(dict.fromkeys(cell['sources']))
            cells[period] = cell
        items.append({'id': site['id'], 'site': site['site'], 'public_id': site['public_id'], 'periods': cells})
    items.sort(key=lambda r: r['site'])
    counts = {}
    for period in PERIODS:
        cells = [r['periods'][period] for r in items]
        counts[period] = {'records': sum(c['conducted'] != '—' for c in cells),
                          'conducted': sum(c['conducted'] == '실시' for c in cells),
                          'not_conducted': sum(c['conducted'] == '미실시' for c in cells),
                          'supplement': sum(c['suitability'] == '보완' for c in cells),
                          'recheck': sum(c['suitability'] == '재확인' or c['conducted'] == '재확인' for c in cells)}
    return {'periods': list(PERIODS), 'period_labels': list(PERIOD_LABELS), 'items': items,
            'counts': counts, 'as_of': datetime.now(timezone.utc).isoformat(),
            'history_as_of': seed['as_of'], 'scope': '전체 현장' if full_scope else '내 담당 현장',
            'can_export': full_scope, 'current_target': len(current_sites) if current_sites is not None else None}


def summary(root, visible_ids, full_scope, current_sites=None):
    root = Path(root)
    seed = json.loads((root / 'training-monitor-history.json').read_text('utf8'))
    states = {}
    with closing(sqlite3.connect((root / 'reviews.sqlite3').resolve().as_uri() + '?mode=ro', uri=True, timeout=10)) as db:
        for key, raw in db.execute('select id,data from contexts'):
            if key.split('|')[-1] in PERIODS and key.split('|')[0] in {s['id'] for s in seed['sites']+(current_sites or [])}:
                states[key] = json.loads(raw)
    return matrix(seed, states, visible_ids, full_scope, current_sites)


def workbook_bytes(value):
    from openpyxl import load_workbook
    workbook = load_workbook(Path(__file__).parent / 'assets/training-monitor-template.xlsx')
    sheet = workbook.active
    last = 5 + len(value['items'])
    for n, item in enumerate(value['items'], 6):
        sheet.cell(n, 1, n - 5)
        sheet.cell(n, 2, item['site'])
        for i, period in enumerate(PERIODS):
            cell = item['periods'][period]
            sheet.cell(n, 3 + i * 2, cell['conducted'])
            sheet.cell(n, 4 + i * 2, cell['suitability'])
    from openpyxl.styles import Alignment
    for row in sheet.iter_rows(min_row=6, max_row=last, max_col=10):
        for cell in row:
            from copy import copy as copied
            cell._style = copied(sheet.cell(6, cell.column)._style)
            cell.alignment = Alignment(horizontal='left' if cell.column == 2 else 'center', vertical='center', wrap_text=True)
        import math, unicodedata
        name = str(sheet.cell(row[0].row, 2).value or '')
        width = sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in name)
        sheet.row_dimensions[row[0].row].height = max(31, 16 * math.ceil(width / 39))
    sheet['A2'] = '기준일 ' + datetime.fromisoformat(value['as_of']).astimezone(__import__('datetime').timezone(__import__('datetime').timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
    for i, label in enumerate(PERIOD_LABELS):
        from openpyxl.utils import get_column_letter
        a, b = get_column_letter(3 + 2 * i), get_column_letter(4 + 2 * i)
        sheet.cell(3, 3 + 2 * i, f'="실시 "&COUNTIF({a}6:{a}{last},"실시")&" / 보완 "&COUNTIF({b}6:{b}{last},"보완")')
    sheet.auto_filter.ref = f'A5:J{last}'
    sheet.print_area = f'A1:J{last}'
    workbook.calculation.fullCalcOnLoad = True
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def export(value):
    return {'filename': '비상훈련_모니터링_2025-2026.xlsx',
            'content_base64': base64.b64encode(workbook_bytes(value)).decode('ascii')}
