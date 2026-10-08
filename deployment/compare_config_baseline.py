from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).parent
BASE=['-i',r'E:\SecureKeys\ssh\besma-ncp-ed25519','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes']
rows=json.loads((R/'config-manifest.json').read_text())['files']
results=[]
for row in rows:
    result=subprocess.run(['ssh',*BASE,'besma-admin@101.79.24.88','sudo -n cat /srv/besma/backend/'+row['path']],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,check=False)
    if result.returncode:
        assert row['before_sha256'] is None
        continue
    old=subprocess.run(['git','-C',str(R/'release'),'show','df25a7e22aacb700e712a30db92fc0197298db1e:backend/'+row['path']],capture_output=True)
    expected=old.stdout if not old.returncode else (R/'runtime-before/backend'/row['path']).read_bytes()
    assert expected.replace(b'\r\n',b'\n')==result.stdout.replace(b'\r\n',b'\n'),row['path']
    target=R/'config-runtime-before'/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result.stdout)
    results.append({'path':row['path'],'line_endings_only':True,'sha256':hashlib.sha256(result.stdout).hexdigest()})
(R/'config-baseline-comparison.json').write_text(json.dumps(results,indent=2),encoding='utf8')
print(json.dumps(results))
