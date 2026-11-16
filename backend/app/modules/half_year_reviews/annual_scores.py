"""Annual standings from verified first-half totals and current saved second-half totals."""
from .aggregate_scores import rounded, rank


def summary(current, config, include_first_half_only=False):
    method = config.get('method', 'AVAILABLE_PERIOD_AVERAGE')
    if method not in {'AVAILABLE_PERIOD_AVERAGE', 'BOTH_PERIODS_AVERAGE'}:
        raise ValueError('ANNUAL_RANKING_METHOD_INVALID')
    first = {r['public_id']: r for r in config.get('h1', []) if r.get('public_id')}
    items = []
    for row in current:
        prior = first.get(row['public_id'])
        items.append({'site': row['site'], 'public_id': row['public_id'], 'first_half': prior['score'] if prior else None, 'second_half': row['scores']['total'], 'state': row['state']})
    if include_first_half_only:
        items.extend({'site': r['site'], 'public_id': None, 'first_half': r['score'], 'second_half': None, 'state': '상반기 평가'} for r in config.get('h1', []) if not r.get('public_id'))
    for item in items:
        values = [item[k] for k in ['first_half', 'second_half'] if item[k] is not None]
        item['periods'] = len(values)
        item['average'] = rounded(sum(values) / len(values)) if values and (method == 'AVAILABLE_PERIOD_AVERAGE' or len(values) == 2) else None
        item['scores'] = {'average': item['average']}
    rank(items, 'average', 'rank')
    for item in items:
        item.pop('scores')
    items.sort(key=lambda r: (r['rank'] is None, r['rank'] or 0, r['site']))
    return {'year': config['year'], 'method': method, 'method_label': config.get('method_label', ''), 'items': items, 'counts': {'sites': len(items), 'ranked': sum(r['rank'] is not None for r in items)}}
