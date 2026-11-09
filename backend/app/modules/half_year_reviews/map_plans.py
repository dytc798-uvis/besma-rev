"""Own pending field evaluations, independent of publication and home-card filters."""
def pending(rows,overview,today,source_codes):
    summaries={s['public_id']:s for s in overview};items=[]
    for row in rows:
        if row.archived_at is not None or row.status not in {'PLANNED','IN_PROGRESS'}:continue
        summary=summaries.get(row.public_id)
        if not summary or summary.get('status')not in {'NOT_STARTED','IN_PROGRESS','COMPLETED'}:raise ValueError('OVERVIEW_UNAVAILABLE')
        if summary['status']=='COMPLETED':continue
        items.append({'public_id':row.public_id,'site_codes':list(dict.fromkeys(source_codes(row))),'site_name':row.title.removeprefix('[점검] ').strip(),
                      'scheduled_date':row.scheduled_date.isoformat(),'period':summary['period'],'status':summary['status']})
    items.sort(key=lambda r:(0,r['scheduled_date'],r['public_id'])if r['scheduled_date']>=today else(1,-int(r['scheduled_date'].replace('-','')),r['public_id']))
    return {'date':today,'items':items}
