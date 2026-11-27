"""Annual assessment average followed by one annual adjustment per site."""
from .aggregate_scores import rounded, rank, adjustments
from decimal import Decimal


def summary(current, config, include_first_half_only=False):
    method = config.get('method', 'AVAILABLE_PERIOD_AVERAGE')
    if method not in {'AVAILABLE_PERIOD_AVERAGE', 'BOTH_PERIODS_AVERAGE'}:
        raise ValueError('ANNUAL_RANKING_METHOD_INVALID')
    first = {r['public_id']: r for r in config.get('h1', []) if r.get('public_id')}
    annual = config.get('annual_adjustments', {})
    def entry(row, prior):
        published = prior['score'] if prior else None
        included = adjustments(prior.get('included_adjustments')) if prior else adjustments()
        first_base = rounded(published-included['net']) if published is not None else None
        key = row['public_id'] or ('h1:'+prior['id'])
        return {'site':row['site'],'public_id':row['public_id'],'first_half':first_base,'first_half_reported':published,'second_half':row['scores']['total'],'state':row['state'],'signature_state':row.get('signature_state'),'provisional':row.get('provisional',False),'adjustments':adjustments(annual.get(key))}
    items = [entry(row,first.get(row['public_id'])) for row in current]
    if include_first_half_only:
        items.extend(entry({'site':r['site'],'public_id':None,'scores':{'total':None},'state':'상반기 평가'},r) for r in config.get('h1',[]) if not r.get('public_id'))
    for item in items:
        values=[item[k] for k in ['first_half','second_half'] if item[k] is not None]
        item['periods']=len(values)
        valid=bool(values) and (method=='AVAILABLE_PERIOD_AVERAGE' or len(values)==2)
        average=sum((Decimal(str(v))for v in values),Decimal(0))/Decimal(len(values)) if valid else None
        item['base_average']=rounded(average) if valid else None
        item['average']=rounded(average+Decimal(str(item['adjustments']['net']))) if valid else None
        item['annual_score']=item['average']
        item['scores']={'average':item['average']}
    rank(items,'average','rank')
    for item in items:item.pop('scores')
    items.sort(key=lambda r:(r['rank']is None,r['rank']or 0,r['site']))
    return {'year':config['year'],'method':method,'method_label':'반기 평균 + 연간 가점 − 연간 감점','items':items,'counts':{'sites':len(items),'ranked':sum(r['rank']is not None for r in items)}}
