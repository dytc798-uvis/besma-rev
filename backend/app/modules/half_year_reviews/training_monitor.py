"""Emergency training matrix. Existing evaluations and historical ledgers stay intact."""
from contextlib import closing
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
import base64, copy, hashlib, io, json, sqlite3

PERIODS = ('2025-H1', '2025-H2', '2026-H1', '2026-H2')
PERIOD_LABELS = ('2025 상반기', '2025 하반기', '2026 상반기', '2026 하반기')
STATES = {'실시', '미실시', '미확인', '재확인', '적합', '보완', '부적합', '—'}


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


def period_bounds(period):
    year=int(period[:4])
    return (date(year,1,1),date(year,6,30)) if period.endswith('H1') else (date(year,7,1),date(year,12,31))


def schedule(period, dates):
    start,end=period_bounds(period)
    try:a=date.fromisoformat(dates['start_date']);b=date.fromisoformat(dates['completion_date'])
    except(KeyError,TypeError,ValueError):return None,False
    if a>b:return None,False
    return a<=end and b>=start,a>end


def collected(historical, data, observed):
    if historical and historical.get('training_received') is True:return True
    if observed=='실시':return True
    if historical and historical.get('receipt_blocked'):return False
    check=(data or {}).get('evidence',{}).get('emergency_drill')or{}
    if not check.get('checked')or check.get('hold'):return False
    for f in (data or {}).get('files',[]):
        if f.get('evidence_id')!='emergency_drill':continue
        name=f.get('filename')or''
        if any(t in name for t in ('계획','시나리오'))and not any(t in name for t in ('결과','교육일지','서명')):continue
        return True
    return False


def lifecycle_rank(row, today):
    try:
        start = date.fromisoformat(row.get('start_date') or '')
        end = date.fromisoformat(row.get('completion_date') or '')
    except ValueError:
        return 2
    if end < start:
        return 2
    if start <= today <= end:
        return 0
    return 3 if end < today else 1


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
        cells = {};dates=seed.get('period_dates',{}).get(site['id'],{})
        for period in PERIODS:
            key = site['id'] + '|' + period
            historical = records.get(key)
            data = states.get(key)
            in_schedule,before_start=schedule(period,dates)
            has_record=bool(historical or data)
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
            observed=cell['conducted'];received=collected(historical,data,observed)
            applicable = in_schedule if in_schedule is not None else has_record
            explicit_no = bool(historical and historical.get('conducted') == '미실시')
            explicit_bad = bool(historical and historical.get('suitability') == '부적합')
            current = relevant(data) if data else {}
            notes = [str((current.get('evidence') or {}).get('note') or '').strip()]
            notes += [str((x or {}).get('note') or '').strip() for x in current.get('answers', {}).values()]
            explicit_no = explicit_no or any(x in ('미실시','훈련 미실시','비상훈련 미실시') for x in notes)
            explicit_bad = explicit_bad or any(x == '부적합' for x in notes)
            source_grade = cell['suitability']
            conducted = 'X' if explicit_no else 'O'
            suitability = '부적합' if explicit_no or explicit_bad else '적합'
            cell.update(observed_conducted=observed,training_received=received,has_record=has_record,in_schedule=in_schedule is True,
                        explicit_nonimplementation=explicit_no,explicit_nonconformity=explicit_bad,
                        source_suitability=source_grade,conducted=conducted if applicable else '—',
                        suitability=suitability if applicable and period.startswith('2026') else '—')
            cell['reasons'] = list(dict.fromkeys(cell['reasons']))
            cell['sources'] = list(dict.fromkeys(cell['sources']))
            cells[period] = cell
        items.append({'id': site['id'], 'site': site['site'], 'public_id': site['public_id'],
                      'start_date':dates.get('start_date'),'completion_date':dates.get('completion_date'),
                      'date_source':dates.get('source'),'periods': cells})
    today = datetime.now(timezone(timedelta(hours=9))).date()
    items.sort(key=lambda r: (lifecycle_rank(r, today), r['site']))
    counts = {}
    for period in PERIODS:
        cells = [r['periods'][period] for r in items]
        counts[period] = {'records': sum(c['conducted'] != '—' for c in cells),
                          'conducted': sum(c['conducted'] == 'O' for c in cells),
                          'not_conducted': sum(c['conducted'] == 'X' for c in cells),
                          'supplement': sum(c['suitability'] == '부적합' for c in cells),
                          'recheck': sum(c['suitability'] == '재확인' or c['conducted'] == '재확인' for c in cells)}
    return {'periods': list(PERIODS), 'period_labels': list(PERIOD_LABELS), 'items': items,
            'counts': counts, 'as_of': datetime.now(timezone.utc).isoformat(),
            'display_policy': '기본 O·적합, 명확한 미실시·부적합만 X·부적합',
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
    columns = ((5,None),(6,None),(7,8),(9,10))
    for n, item in enumerate(value['items'], 6):
        sheet.cell(n, 1, n - 5)
        sheet.cell(n, 2, item['site'])
        for col,key in [(3,'start_date'),(4,'completion_date')]:
            sheet.cell(n,col,date.fromisoformat(item[key])if item.get(key)else None).number_format='yy"/"mm"/"dd'
        for i, period in enumerate(PERIODS):
            cell = item['periods'][period]
            a,b=period_bounds(period)
            bound=lambda d:f'DATE({d.year},{d.month},{d.day})'
            overlap=f'AND(ISNUMBER($C{n}),ISNUMBER($D{n}),$C{n}<={bound(b)},$D{n}>={bound(a)})'
            eligible=f'IF(AND(ISNUMBER($C{n}),ISNUMBER($D{n}),$C{n}<=$D{n}),{overlap},{"TRUE"if cell["has_record"]else"FALSE"})'
            col,grade_col=columns[i]
            sheet.cell(n,col,f'=IF({eligible},"'+('X'if cell['explicit_nonimplementation']else'O')+'","—")')
            if grade_col:
                grade='부적합'if cell['explicit_nonimplementation']or cell['explicit_nonconformity']else'적합'
                sheet.cell(n,grade_col,f'=IF({eligible},"'+grade+'","—")')
    from openpyxl.styles import Alignment
    for row in sheet.iter_rows(min_row=6, max_row=last, max_col=10):
        for cell in row:
            from copy import copy as copied
            cell._style = copied(sheet.cell(6, cell.column)._style)
            cell.alignment = Alignment(horizontal='left' if cell.column == 2 else 'center', vertical='center', wrap_text=True)
        import math, unicodedata
        name = str(sheet.cell(row[0].row, 2).value or '')
        width = sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in name)
        sheet.row_dimensions[row[0].row].height = max(31, 16 * math.ceil(width / 33))
    sheet['A2'] = '기준일 ' + datetime.fromisoformat(value['as_of']).astimezone(__import__('datetime').timezone(__import__('datetime').timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
    for i, label in enumerate(PERIOD_LABELS):
        from openpyxl.utils import get_column_letter
        col,_=columns[i];a=get_column_letter(col)
        sheet.cell(3,col,f'="O "&COUNTIF({a}6:{a}{last},"O")&" / X "&COUNTIF({a}6:{a}{last},"X")')
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import PatternFill
    sheet.conditional_formatting._cf_rules.clear()
    for i,period in enumerate(PERIODS):
        a,b=period_bounds(period);col,grade_col=columns[i];left=get_column_letter(col);right=get_column_letter(grade_col or col)
        formula=f'AND(ISNUMBER($C6),ISNUMBER($D6),$C6<=$D6,$C6<=DATE({b.year},{b.month},{b.day}),$D6>=DATE({a.year},{a.month},{a.day}))'
        sheet.conditional_formatting.add(f'{left}6:{right}{last}',FormulaRule(formula=[formula],fill=PatternFill('solid',fgColor='FFFCE4D6',bgColor='FFFCE4D6')))
    sheet.conditional_formatting.add(f'E6:J{last}',FormulaRule(formula=['TRUE'],fill=PatternFill('solid',fgColor='FFEDEDED',bgColor='FFEDEDED')))
    sheet.auto_filter.ref = f'A5:J{last}'
    sheet.print_area = f'A1:J{last}'
    workbook.calculation.fullCalcOnLoad = True
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def export(value):
    return {'filename': '비상훈련_모니터링_2025-2026.xlsx',
            'content_base64': base64.b64encode(workbook_bytes(value)).decode('ascii')}
