"""Administrative fixed-path inbox for derived daily ERP data. Does not touch evaluation tables."""
import argparse,datetime as dt,hashlib,json,os,re,sys
from pathlib import Path
ROOT=Path('/srv/besma/storage/headquarters-workspace/daily-attendance')
def validate(data):
    if set(data)!={'schema','date','captured_at','source_sha256','source_filename','people','unidentified_people','sites','identities'}:raise ValueError('SCHEMA_FIELDS')
    day=dt.date.fromisoformat(data['date']);now=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    captured=dt.datetime.fromisoformat(data['captured_at'])
    if captured.tzinfo is None or captured.astimezone(now.tzinfo).date()!=day or day>now.date():raise ValueError('DATE')
    if data['schema']!=1 or not re.fullmatch('[0-9a-f]{64}',data['source_sha256']):raise ValueError('SOURCE')
    if not isinstance(data['people'],int) or not 0<=data['people']<=100000:raise ValueError('COUNT')
    if len(data['identities'])!=data['people'] or sum(s['people'] for s in data['sites'])!=data['people']:raise ValueError('COUNT_MISMATCH')
    for person in data['identities']:
        if set(person)!={'rrn_hash','site_code'} or person['rrn_hash'] is not None and not re.fullmatch('[0-9a-f]{64}',person['rrn_hash']):raise ValueError('IDENTITY_FIELDS')
    for site in data['sites']:
        if set(site)!={'code','name','people'} or not isinstance(site['people'],int) or site['people']<0:raise ValueError('SITE_FIELDS')
    if any(not isinstance(s['name'],str) or len(s['name'])>600 for s in data['sites']):raise ValueError('SITE_NAME')
    return data
def catalog():
    sys.path.insert(0,'/srv/besma/backend')
    import sqlite3
    path=Path('/srv/besma/storage/site-directory/directory.json');d=json.loads(path.read_text(encoding='utf-8'))
    with sqlite3.connect('file:/srv/besma/database/besma.db?mode=ro',uri=True) as c:rows=c.execute('SELECT site_code,site_name FROM sites').fetchall()
    return {'aliases':d.get('aliases',{}),'sites':[{'code':s['code'],'name':s['name']} for s in d['sites']]+[{'code':code,'name':name} for code,name in rows]}
def main():
    import grp
    p=argparse.ArgumentParser();p.add_argument('source',nargs='?',type=Path);p.add_argument('--catalog',action='store_true');a=p.parse_args()
    if a.catalog:print(json.dumps(catalog(),ensure_ascii=True));return
    if os.geteuid()!=0:raise PermissionError('ADMIN_REQUIRED')
    source=a.source.resolve()
    if source.parent!=Path('/home/besma-admin/.besma-workspace-attendance-inbox') or not re.fullmatch(r'besma-daily-attendance-\d{8}-[0-9a-f]{12}\.json',source.name) or source.stat().st_size>50_000_000:raise ValueError('FIXED_INBOX_REQUIRED')
    body=source.read_bytes();data=validate(json.loads(body));gid=grp.getgrnam('besma').gr_gid;os.umask(0o027)
    folder=ROOT/data['date'];folder.mkdir(parents=True,exist_ok=True)
    for d in (ROOT,folder):os.chown(d,0,gid);d.chmod(0o750)
    digest=hashlib.sha256(body).hexdigest();version=folder/(data['captured_at'].replace(':','').replace('+','_')+'-'+digest[:12]+'.json')
    def write(path):
        temp=path.with_name(path.name+'.new');temp.write_bytes(body);os.chown(temp,0,gid);temp.chmod(0o640);os.replace(temp,path)
    if version.exists():
        if version.read_bytes()!=body:raise ValueError('IMMUTABLE_VERSION_CONFLICT')
    else:write(version)
    latest=ROOT/'latest.json';updated=True
    if latest.exists():
        prior=json.loads(latest.read_text(encoding='utf-8'))
        updated=(data['date'],data['captured_at'])>(prior['date'],prior['captured_at'])
        if (data['date'],data['captured_at'])==(prior['date'],prior['captured_at']) and prior['source_sha256']!=data['source_sha256']:raise ValueError('SAME_CAPTURE_CONFLICT')
    if updated:write(latest)
    print(json.dumps({'date':data['date'],'people':data['people'],'sites':len(data['sites']),'latest_updated':updated,'sha256':digest,'database_changed':False}))
if __name__=='__main__':main()
