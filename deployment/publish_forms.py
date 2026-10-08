"""Prepare six reviewed copies without changing or disclosing internal originals."""
import hashlib,json,os,shutil,sys
from pathlib import Path
sys.path.insert(0,'/srv/besma/backend')
from app.config.settings import settings
from app.modules.document_explorer.government_access import PUBLIC_CANDIDATE_RELATIVE_PATHS
root=Path(settings.document_explorer_base_dir)
expected=json.loads(Path(__file__).with_name('public-form-hashes.json').read_text(encoding='utf8'))
receipt=[]
for rel in sorted(PUBLIC_CANDIDATE_RELATIVE_PATHS):
    source=root/'일반 양식'/rel;dest=root/'관급 공개 양식'/rel
    assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest()==expected[rel],('PUBLIC_CANDIDATE_SOURCE_CHANGED',rel)
    if dest.exists():
        assert hashlib.sha256(dest.read_bytes()).hexdigest()==expected[rel],('PUBLIC_COPY_ALREADY_DIFFERENT',rel)
    else:
        dest.parent.mkdir(parents=True,exist_ok=True,mode=0o750)
        with dest.open('xb') as f:f.write(source.read_bytes());f.flush();os.fsync(f.fileno())
        os.chmod(dest,0o640)
    receipt.append({'relative_path':rel,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
Path(__file__).with_name('public-form-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'prepared_copies':len(receipt),'visibility_policy_changed':False}))
