"""Publish verified anonymous opinion counts after an existing monthly collection."""
from pathlib import Path
from datetime import datetime,timezone
import sqlite3,json,hashlib,re,base64

def prepare(root):
    root=Path(root);con=sqlite3.connect((root/'ledger.sqlite3').as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    try:
        snapshot=json.loads((root/'dashboard.json').read_text('utf8'));current={r['id']:r for r in snapshot['items']};grouped={};skipped=0
        for item in con.execute('SELECT o.*,f.site_code,f.sha256,f.state,f.nas_path,d.sha256 delivery_sha,d.size delivery_size FROM opinions o JOIN files f ON o.source_id=f.id LEFT JOIN deliveries d ON d.file_id=f.id ORDER BY o.id'):
            row=current.get(item['source_id'])
            if not row or row.get('category')!='opinions' or row.get('state')!='SAVED' or not row.get('site_code') or row['sha256']!=item['sha256'] or row['site_code']!=item['site_code']:skipped+=1;continue
            if item['source_id']not in grouped:
                target=Path(item['nas_path'])
                if not item['delivery_sha']or not target.is_file()or target.stat().st_size!=item['delivery_size']or hashlib.sha256(target.read_bytes()).hexdigest()!=item['delivery_sha']:skipped+=1;continue
                grouped[item['source_id']]={k:row[k]for k in ['id','site_code','sha256','month']};grouped[item['source_id']]['opinions']=[]
            content=re.sub(r'\s+','',item['opinion']or'')
            if item['status']in {'의견 없음','의견란 공란'}or content in {'','없음','의견없음','해당없음','특이사항없음','-'}:continue
            try:datetime.fromisoformat(item['day'])
            except (ValueError,TypeError):skipped+=1;continue
            identity='|'.join([row['site_code'],item['day'],re.sub(r'\s+','',item['person']or''),content])
            oid=hashlib.sha256(identity.encode()).hexdigest()
            grouped[item['source_id']]['opinions'].append({'id':oid,'day':item['day']})
        return {'schema':1,'generated_at':datetime.now(timezone.utc).isoformat(),'source_generation':snapshot['generated_at'],'sources':list(grouped.values()),'skipped':skipped}
    finally:con.close()

def publish(root,transport):
    value=prepare(root);raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode();wire=base64.b64encode(raw).decode();digest=hashlib.sha256(raw).hexdigest()
    script='''import pathlib,json,base64,hashlib,os
root=pathlib.Path('/srv/besma/monthly-collection');raw=base64.b64decode(WIRE);assert hashlib.sha256(raw).hexdigest()==DIGEST
v=json.loads(raw);assert v['schema']==1 and len(raw)<1048576
current=json.loads((root/'current.json').read_bytes());idx={r['id']:r for r in current['items']}
for r in v['sources']:
 assert r['id']in idx and all(r[k]==idx[r['id']][k]for k in ['sha256','site_code','month'])
target=root/'opinion-counts.json';tmp=root/'opinion-counts.tmp';tmp.write_bytes(raw);tmp.chmod(0o640);os.replace(tmp,target)
assert hashlib.sha256(target.read_bytes()).hexdigest()==DIGEST
print(json.dumps({'published':True,'sha256':DIGEST,'sources':len(v['sources']),'opinions':len({i['id']for r in v['sources']for i in r['opinions']}),'skipped':v['skipped']}))
'''.replace('WIRE',repr(wire)).replace('DIGEST',repr(digest))
    result=transport(script);(Path(root)/'opinion-score-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');return result
