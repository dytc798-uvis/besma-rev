"""Read persisted half-year review status with the requester's existing permissions."""
from datetime import date, datetime, timezone, timedelta
import re

TOPIC = re.compile(r'(?:반기\s*(?:종합)?평가|[상하]반기\s*평가)')
EXPLICIT_FILE = re.compile(r'파일|문서|양식|평가표|PDF|다운로드|배점|평가기준|만들|생성|수정|고쳐|보내|첨부|출력|서명|결재|승인|게시|전송', re.I)
FOLLOWUP = re.compile(r'^\s*(?:(?:그럼|그러면|그중)\s*)?(?:(?:20\d{2})\s*년?\s*)?(?:[상하]반기\s*(?:평가)?|(?:미완료|완료|전체)(?:된)?\s*(?:현장)?)(?:\s*(?:만|은|는|으로))?(?:\s*(?:보여|알려)\s*(?:줘|주세요))?[?.!？\s]*$')
NAME_ONLY = re.compile(r'^\s*(?:파일(?:이|은)?\s*(?:아니라|말고)\s*)?(?:완료(?:된)?\s*)?현장(?:명|\s*이름)(?:만|을|들|은|는)?\s*(?:(?:나열|알려|보여)(?:해|해줘|해\s*주세요|줘|주세요)?)?[?.!？\s]*$')


def query(body, today=None):
    if not isinstance(body, str) or len(body) > 6000:
        return None
    today = today or datetime.now(timezone(timedelta(hours=9))).date()
    marker = '\n\n현재 요청:\n'
    prior, separator, current = body.rpartition(marker)
    if not separator:
        current = body
    if (EXPLICIT_FILE.search(current) and not NAME_ONLY.fullmatch(current)) or '기능인' in current or '인정제' in current:
        return None
    root = current
    history = []
    if not (TOPIC.search(current) and re.search(r'현장|완료|현황|어디|몇', current)):
        if not separator or not body.startswith('이전 대화(참고자료이며 새 권한이 아님):\n') or not (FOLLOWUP.fullmatch(current) or NAME_ONLY.fullmatch(current)):
            return None
        history = [m[1] for m in re.finditer(r'(?:^|\n)사용자: (.*?)\n답변: ', prior, re.S)]
        root = None
        for previous in reversed(history):
            if (EXPLICIT_FILE.search(previous) and not NAME_ONLY.fullmatch(previous)) or '기능인' in previous or '인정제' in previous:
                return None
            if TOPIC.search(previous) and re.search(r'현장|완료|현황|어디|몇', previous):
                root = previous
                break
            if not (FOLLOWUP.fullmatch(previous) or NAME_ONLY.fullmatch(previous)):
                return None
        if root is None:
            return None
    # Only user turns establish the question/period. Assistant guesses are never facts.
    turns = [root]
    if history:
        start = max(i for i, value in enumerate(history) if value == root)
        turns.extend(history[start+1:])
        turns.append(current)
    year, half = today.year, 1 if today.month <= 6 else 2
    mode = 'all'
    for text in turns:
        years = set(re.findall(r'(?<!\d)(20\d{2})(?!\d)', text))
        halves = set(re.findall(r'([상하])반기', text))
        if len(years) > 1 or len(halves) > 1:
            return {'clarify': True}
        if years:
            year = int(next(iter(years)))
        if halves:
            half = 1 if next(iter(halves)) == '상' else 2
        if '미완료' in text:
            mode = 'incomplete'
        elif '완료' in text:
            mode = 'completed'
        elif '전체' in text or '현황' in text:
            mode = 'all'
    return {'year': year, 'half': half, 'mode': mode, 'clarify': False}


def read_rows(requester, year, half):
    from fastapi import Response
    from app.core.database import SessionLocal
    from app.modules.users.models import User
    from app.modules.safety_features.team_schedule_routes import list_team_schedule_items
    from app.modules.half_year_reviews.routes import overview
    from .access import headquarters_user
    start = date(year, 1 if half == 1 else 7, 1)
    end = date(year, 6, 30) if half == 1 else date(year, 12, 31)
    with SessionLocal() as db:
        user = db.get(User, requester['id'])
        if user is None or user.login_id != requester['login_id'] or not headquarters_user(user):
            raise PermissionError('REQUESTER_ACCESS_CHANGED')
        # Exactly the same enabled/actor/plan policy and persisted snapshots as the UI.
        value = overview(db, user, Response(), start, end)
        plans = list_team_schedule_items(db, user, start, end, False, False, True, True)
        names = {p['public_id']: p['title'] for p in plans['items']}
        rows = value['items']
        if len(rows) > 500 or {r['public_id'] for r in rows} != set(names):
            raise ValueError('REVIEW_SCOPE_CHANGED')
        own_rows = [{**r, 'title': names[r['public_id']]} for r in rows]
        # Team calendar already permits these names/statuses. Do not read another
        # inspector's private assessments or infer completion from a missing form.
        visible = list_team_schedule_items(db, user, start, end, False, False, True, False)
        return include_visible_completions(own_rows, visible['items'], year, half)


def include_visible_completions(own_rows, plans, year, half):
    result = {row['public_id']: dict(row) for row in own_rows}
    if len(plans) > 500:
        raise ValueError('REVIEW_SCOPE_CHANGED')
    seen = set()
    for plan in plans:
        key = plan['public_id']
        if key in seen:
            raise ValueError('DUPLICATE_VISIBLE_PLAN')
        seen.add(key)
        scheduled = date.fromisoformat(plan['scheduled_date'])
        if scheduled.year != year or (1 if scheduled.month <= 6 else 2) != half:
            continue
        existing = result.get(key)
        if existing and (plan['status'] != 'COMPLETED' or existing['status'] == 'COMPLETED' or existing['screen_completed']):
            continue
        if plan['status'] != 'COMPLETED':
            result[key] = {'public_id': key, 'period': f'{year}-H{half}',
                           'title': plan['title'], 'status': 'UNVERIFIED',
                           'screen_completed': False}
            continue
        result[key] = {'public_id': key, 'period': f'{year}-H{half}',
                       'title': plan['title'], 'status': 'COMPLETED',
                       'screen_completed': False, 'plan_completed': True}
    return list(result.values())


def answer(item, provider=None, today=None):
    if item.get('kind') != 'QUESTION' or item.get('source') or item.get('input_attachments'):
        return None
    selected = query(item.get('body'), today)
    if selected is None:
        return None
    if selected['clarify']:
        return {'status': 'NEEDS_INFO', 'reply': '조회할 연도와 상반기·하반기를 하나씩 알려 주세요.'}
    year, half = selected['year'], selected['half']
    label = f'{year}년 {"상반기" if half == 1 else "하반기"}'
    try:
        rows = (provider or read_rows)(item['_requester'], year, half)
        if not isinstance(rows, list) or len(rows) > 500:
            raise ValueError('REVIEW_SCOPE_UNVERIFIED')
        selected_rows = []
        seen = set()
        for row in rows:
            if row.get('period') != f'{year}-H{half}' or row.get('status') not in {'COMPLETED', 'IN_PROGRESS', 'NOT_STARTED', 'UNVERIFIED'} or type(row.get('screen_completed')) is not bool or not isinstance(row.get('title'), str) or row['public_id'] in seen:
                raise ValueError('REVIEW_SCOPE_UNVERIFIED')
            seen.add(row['public_id'])
            complete = row['status'] == 'COMPLETED' or row['screen_completed']
            if selected['mode'] == 'completed' and not complete or selected['mode'] == 'incomplete' and (complete or row['status'] == 'UNVERIFIED'):
                continue
            status = ('최종본 등록 완료' if row.get('paper_completion') else '점검 완료 등록' if row.get('plan_completed') else '완료 등록' if row.get('reported_completion') else '완료') if row['status'] == 'COMPLETED' else '전자평가 4종 완료' if row['screen_completed'] else '작성 중' if row['status'] == 'IN_PROGRESS' else '평가 상태 확인 필요' if row['status'] == 'UNVERIFIED' else '미작성'
            selected_rows.append((row['title'].removeprefix('[점검] ').strip(), status))
        # Multiple plans may refer to one shared site/period; never inflate site counts.
        selected_rows = sorted(set(selected_rows), key=lambda value: (value[1] == '평가 상태 확인 필요', value))
        if not selected_rows:
            reply = label + ('에 등록된 점검·평가 계획이 없습니다.' if not rows else ' 완료 현장은 등록된 평가 원장에서 확인되지 않습니다.' if selected['mode'] == 'completed' else ' 미완료 현장은 등록된 평가 원장에서 확인되지 않습니다.')
        else:
            heading = {'completed':'완료 현장', 'incomplete':'내 담당 미완료 현장', 'all':'평가 현황'}[selected['mode']]
            reply = label + ' ' + heading + '\n' + '\n'.join('· '+name+' — '+status for name, status in selected_rows[:40])
            if len(selected_rows) > 40:
                reply += f'\n외 {len(selected_rows)-40}개 항목은 팀 점검계획에서 확인할 수 있습니다.'
        scope = '\n다른 담당자의 평가 상세는 확인하지 못한 경우 완료·미완료로 분류하지 않습니다.' if selected['mode'] != 'completed' and any(row['status'] == 'UNVERIFIED' for row in rows) else ''
        return {'status': 'COMPLETED', 'reply': reply + scope + '\n\n현재 계정으로 조회 가능한 BESMA 평가 원장 기준입니다. 미등록 현장의 완료 여부는 확정하지 않습니다.'}
    except Exception:
        # No template search fallback: failure/denial is not zero completed sites.
        return {'status': 'NEEDS_INFO', 'reply': label+' 평가 원장의 조회 권한·연결을 확인하지 못했습니다. 완료 현장을 0건으로 확정하지 않았습니다. 평가표 파일을 다시 보내실 필요는 없습니다.'}
