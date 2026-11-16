"""Explicit, period-specific headquarters awards; field completion stays separate."""
from copy import deepcopy
from uuid import uuid4
from .catalog import validate_assessment
from .supervisor_group import project_data


def seed(data, form, answers):
    award = data.get('headquarters_evaluation')
    if form != 'manager' or not award:
        return
    entry = answers.setdefault('answers', {}).setdefault('m10', {'value': None, 'note': ''})
    if entry.get('value') is None:
        entry['value'] = award['score']


def award(data, score, actor, name, stamp, revision):
    if actor != 96 or type(score) is not int or not 0 <= score <= 7:
        raise ValueError('HEADQUARTERS_SCORE_INVALID')
    previous = data.get('headquarters_evaluation')
    if previous:
        data.setdefault('headquarters_award_history', []).append(deepcopy(previous))
    data['headquarters_evaluation'] = {'score': score, 'actor_id': actor, 'by': name, 'at': stamp}
    changed = []
    for key, record in data['assessments'].items():
        if not key.startswith('manager:'):
            continue
        subject = key.split(':', 1)[1]
        for slot in ['draft', 'completed']:
            prior = record.get(slot)
            if not prior or prior['data']['answers'].get('m10', {}).get('value') == score:
                continue
            snapshot = deepcopy(prior)
            entry = snapshot['data']['answers'].setdefault('m10', {'note': ''})
            entry['value'] = score
            _, result = validate_assessment('manager', snapshot['data'], data['files'], project_data(data)['subjects'], subject, False)
            snapshot['result'] = result
            snapshot['headquarters_award'] = deepcopy(data['headquarters_evaluation'])
            if slot == 'completed':
                snapshot['id'] = uuid4().hex
                snapshot['revision'] = revision
            data.setdefault('headquarters_score_history', []).append({'assessment': key, 'slot': slot, 'previous': deepcopy(prior), 'at': stamp, 'actor_id': actor})
            record[slot] = snapshot
            changed.append(key + '/' + slot)
    return {'score': score, 'updated_snapshots': changed}
