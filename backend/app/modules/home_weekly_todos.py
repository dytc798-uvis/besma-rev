"""Personal, read-only carryover tasks from registered weekly meeting results."""
from datetime import date, datetime, timedelta
import re
from typing import Annotated
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Response
from app.core.auth import DbDep, get_current_user
from app.modules.users.models import User

router = APIRouter(prefix='/workspace', tags=['workspace'])

# Reviewed meeting-to-plan links: 261116 H6/H8/H9/H16, same assignee/date.
# These are identifiers only; authorization is rechecked against both rows.
REVIEWED_LINKS = {
    'f29e1fae-f622-4ca8-8aa0-d1145f927589': '8287ea0a-f7d8-4164-9abe-327e4c47a908',
    '1a4237c8-75f9-41da-b4ef-f38a3504fcce': '077e2830-d51a-4ba9-911f-638eabfdd272',
    '91e80be5-6c93-4840-a859-49d19d195f6e': '5e7ff536-a933-43ca-9745-e64e5462ffb8',
    'c600e968-dd68-4f32-8c20-f6d8383ffcab': '654ab973-de2a-474c-9909-a1d7e69801ca',
}

def previous_week(today):
    monday = today - timedelta(days=today.weekday())
    return monday - timedelta(days=7), monday - timedelta(days=1), monday

def meeting_result(row, today):
    first, last, monday = previous_week(today)
    if not first <= row.scheduled_date <= last:
        return False
    # Imported schedule dates can be moved. Verify the original meeting date,
    # results column and stated work date rather than treating a moved row as new.
    detail = row.detail_text or ''
    source = re.search(r'주간회의록 (\d{6}) / ([HJ])\d+\b', detail)
    if not source or source.group(1) != monday.strftime('%y%m%d') or source.group(2) != 'H':
        return False
    stated = re.search(r'\((\d{1,2})/(\d{1,2})\)', detail)
    return bool(stated and (int(stated[1]), int(stated[2])) == (row.scheduled_date.month, row.scheduled_date.day))

def evaluation_state(item):
    if item.get('paper_completion') or item.get('reported_completion') or (item.get('screen_completed') and item.get('signature_completed')):
        return 'COMPLETED'
    if item.get('status') == 'IN_PROGRESS' or item.get('screen_completed'):
        return 'IN_PROGRESS'
    return 'NOT_STARTED'

def normalized_title(value):
    return re.sub(r'\s+|\[점검\]|반기평가|점검', '', value or '')

@router.get('/my-weekly-todos')
def my_weekly_todos(db: DbDep, user: Annotated[User, Depends(get_current_user)], response: Response):
    from app.modules.safety_features.team_schedule_models import TeamScheduleItem
    from app.modules.safety_features.team_schedule_routes import _member_or_403, _linked_schedule_access
    from app.modules.half_year_reviews.routes import store, enabled
    from app.modules.half_year_reviews.overview import summaries
    _member_or_403(db, user)
    enabled(db, user)
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    first, last, monday = previous_week(today)
    rows = db.query(TeamScheduleItem).filter(
        TeamScheduleItem.assigned_user_id == user.id,
        TeamScheduleItem.archived_at.is_(None),
        TeamScheduleItem.scheduled_date >= first,
        TeamScheduleItem.scheduled_date <= last,
        TeamScheduleItem.source.in_(['WEEKLY_MEETING', 'INSPECTION_PLAN']),
    ).order_by(TeamScheduleItem.scheduled_date, TeamScheduleItem.id).all()
    rows = [r for r in rows if _linked_schedule_access(db, r, user.id)]
    meetings = [r for r in rows if r.source == 'WEEKLY_MEETING' and meeting_result(r, today)]
    plans = [r for r in rows if r.source == 'INSPECTION_PLAN']
    values = {v['public_id']: v for v in summaries(store().root, plans)}
    active, completed, seen = [], 0, set()
    for row in meetings:
        candidates = [p for p in plans if p.scheduled_date == row.scheduled_date and
                      (p.public_id == REVIEWED_LINKS.get(row.public_id) or
                       normalized_title(p.title) == normalized_title(row.title))]
        plan = candidates[0] if len(candidates) == 1 else None
        key = plan.public_id if plan else row.public_id
        if key in seen:
            continue
        seen.add(key)
        state = evaluation_state(values[plan.public_id]) if plan else ('COMPLETED' if row.status == 'COMPLETED' else 'NOT_STARTED')
        if state == 'COMPLETED':
            completed += 1
            continue
        active.append({'public_id': row.public_id, 'title': row.title,
                       'date': row.scheduled_date.isoformat(), 'status': state,
                       'plan_id': plan.public_id if plan else None,
                       'evaluation_linked': bool(plan)})
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Authorization'
    return {'week_start': first.isoformat(), 'week_end': last.isoformat(),
            'meeting_date': monday.isoformat(), 'count': len(active),
            'completed_count': completed, 'items': active}
