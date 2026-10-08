from pathlib import Path
import json,hashlib,subprocess,tarfile
R=Path(__file__).parent;ROOT=R.parent;baseline='6036f89afee9293ecec55319e869c6be34fe76a3';files=[]
for name in ['routes.py','models.py']:
    path='app/modules/government_contact/'+name
    data=subprocess.check_output(['git','-C',str(ROOT/'release'),'show',baseline+':backend/'+path])
    observed=R/('before-'+name)
    if observed.exists():
        actual=observed.read_bytes();assert actual.replace(b'\r\n',b'\n')==data.replace(b'\r\n',b'\n');data=actual
    files.append({'path':path,'before_sha256':hashlib.sha256(data).hexdigest(),'sha256':hashlib.sha256((ROOT/'release/backend'/path).read_bytes()).hexdigest()})
head=subprocess.check_output(['git','-C',str(ROOT/'release'),'rev-parse','HEAD'],text=True).strip();(R/'manifest.json').write_text(json.dumps({'version':'government-contact-1.4.0','commit':head,'files':files},indent=2),encoding='utf8')
with tarfile.open(R/'release.tar.gz','w:gz') as t:
    t.add(ROOT/'release/backend',arcname='backend',filter=lambda i:None if '__pycache__' in i.name else i)
    for name in ('server.py','manifest.json'):t.add(R/name,arcname=name)
print(json.dumps({'files':len(files),'commit':head}))
