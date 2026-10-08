from pathlib import Path
import json,hashlib,subprocess,tarfile
R=Path(__file__).parent;release=R/'release';baseline='df25a7e22aacb700e712a30db92fc0197298db1e'
paths=['app/core/database.py','app/modules/collection_monitor/core.py','app/modules/collection_monitor/nas_export.py','app/modules/collection_monitor/routes.py','app/modules/collection_monitor/models.py','app/modules/collection_monitor/configuration.py','app/modules/document_submissions/routes.py']
rows=[]
for path in paths:
    previous=subprocess.run(['git','-C',str(release),'show',baseline+':backend/'+path],capture_output=True)
    if previous.returncode:
        # This production route was unchanged, and part of the frozen runtime baseline.
        p=R/'runtime-before/backend'/path;data=p.read_bytes() if p.exists() else None
    else:data=previous.stdout
    observed=R/'config-runtime-before'/path
    if observed.exists():
        actual=observed.read_bytes();assert data is not None and actual.replace(b'\r\n',b'\n')==data.replace(b'\r\n',b'\n');data=actual
    rows.append({'path':path,'before_sha256':hashlib.sha256(data).hexdigest() if data is not None else None,'sha256':hashlib.sha256((release/'backend'/path).read_bytes()).hexdigest()})
head=subprocess.check_output(['git','-C',str(release),'rev-parse','HEAD'],text=True).strip();manifest={'version':'collection-monitor-1.3.0-configurable-folders','commit':head,'files':rows};(R/'config-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
source=(R/'operations.py').read_text(encoding='utf8').replace("len(payload['sites'])==8","len(payload['sites'])==6").replace('4+56','4+42');(R/'config-operations.py').write_text(source,encoding='utf8')
with tarfile.open(R/'config.tar.gz','w:gz') as t:
    t.add(release/'backend',arcname='release/backend',filter=lambda i:None if '__pycache__' in i.name else i)
    for src,dest in [('config_server.py','config_server.py'),('config-operations.py','operations.py'),('config-manifest.json','config-manifest.json'),('site-contacts-20261008.json','site-contacts-20261008.json')]:t.add(R/src,arcname=dest)
print(json.dumps({'backend_files':len(rows),'commit':head}))
