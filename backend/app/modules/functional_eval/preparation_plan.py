"""Preparation settings never create, activate or reopen an evaluation period."""
import json
from datetime import date
from pathlib import Path

PLAN_PATH = Path(__file__).with_name('preparation_plan.json')


def preparation_plan(path=None):
    base = {'state': 'PREPARING', 'can_evaluate': False, 'auto_start': False,
            'worker_scope': 'ALL_WORKERS', 'whole_roster_verified': False,
            'attendance_scope': 'DAILY_ATTENDANCE_ONLY',
            'target_start': None, 'deadline': None, 'evaluation_mode': None}
    try:
        value = json.loads(Path(path or PLAN_PATH).read_text(encoding='utf-8'))
        if (value.get('schema') != 1 or value.get('auto_start') is not False
                or value.get('mode') not in {'PERIODIC', 'CONTINUOUS'}):
            raise ValueError('INVALID_PREPARATION_PLAN')
        start = date.fromisoformat(value['planned_start'])
        end = date.fromisoformat(value['deadline']) if value.get('deadline') else None
        if (end and end < start) or (value['mode'] == 'CONTINUOUS' and end):
            raise ValueError('INVALID_PREPARATION_RANGE')
        return {**base, 'target_start': start.isoformat(),
                'deadline': end.isoformat() if end else None,
                'evaluation_mode': value['mode'], 'plan_valid': True}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {**base, 'state': 'CHECK_REQUIRED', 'plan_valid': False}
