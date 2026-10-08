"""Central approved PC transport, invoked over existing verified SSH, never embedded in the app."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from app.config.settings import settings
from .core import CATEGORIES,GOV_CATEGORY,readonly,state,sites,government_documents,ingest,now

ROOT=Path(settings.storage_root)/"collection-monitor"

def export(month):
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o750)
    stage=Path(tempfile.mkdtemp(prefix="out-",dir=ROOT))
    items=[]
    storage=Path(settings.storage_root).resolve()
    with readonly(settings.sqlite_path) as main,state(ROOT) as c:
        documents=government_documents(main)
        versions=list(documents)
        for d in documents:
            for h in main.execute('SELECT version_no,file_name,file_path,file_size,uploaded_at FROM document_upload_histories WHERE document_id=? AND file_path IS NOT NULL',(d['id'],)):
                if h['version_no']==d['version_no']:continue
                versions.append({**d,**dict(h),'original_file_path':None})
        emitted=set()
        for d in versions:
            p=Path(d["original_file_path"] or d["file_path"])
            if not p.is_absolute(): p=storage/p
            if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(storage): continue
            sha=hashlib.sha256(p.read_bytes()).hexdigest()
            key=f"{d['id']}-{d['version_no']}-{sha}"
            if key in emitted:continue
            emitted.add(key)
            if c.execute("SELECT 1 FROM mirrors WHERE key=?",(key,)).fetchone(): continue
            category=GOV_CATEGORY[d["code"]]
            day=d["period_start"] or str(d["uploaded_at"])[:10]
            if not day or day=="None": continue
            if category=='nonconformity' and d.get('period_end'):day=d['period_end'][:10]
            ym=day[:7]
            yy,mm=ym.split("-")
            folder=f"{yy[2:]}.{mm}월"
            # Match each existing category's period / team topology.
            parts=[CATEGORIES[category][1]]
            if category=="nonconformity": parts += ["관급",folder,f"{folder} {(int(day[8:10])-1+date.fromisoformat(day).replace(day=1).weekday())//7+1}주차"]
            else: parts += [folder,"관급"]
            title=main.execute('SELECT title FROM document_requirements WHERE site_id=? AND code=? LIMIT 1',(d['site_id'],d['code'])).fetchone()
            label=re.sub(r'[\\/:*?"<>|\x00-\x1f]',"_",title[0] if title else d['code']).removeprefix('관급 ')
            sitelabel=re.sub(r'[\\/:*?"<>|\x00-\x1f]',"_",re.sub(r'^\[[^]]+\]\s*','',d['site_name']))[:80]
            parts += [d["site_code"]+' '+sitelabel,label]
            name=re.sub(r'[\\/:*?"<>|\x00-\x1f]',"_",d["file_name"] or p.name)
            name=f"{d['site_code']}_문서{d['id']}_v{d['version_no']}_{sha[:10]}_{name}"[:220]
            rel="/".join(parts+[name])
            shutil.copyfile(p,stage/key)
            items.append({"key":key,"sha256":sha,"size":p.stat().st_size,"relative_path":rel})
    manifest={"items":items,"created_at":now()}
    (stage/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False),encoding="utf8")
    out=stage.with_suffix(".zip")
    with zipfile.ZipFile(out,"x",zipfile.ZIP_DEFLATED) as z:
        for p in stage.iterdir(): z.write(p,p.name)
    return {"bundle":str(out),"count":len(items)}

def accept(bundle):
    path=Path(bundle).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.is_symlink(): raise ValueError("INVALID_TRANSFER_ROOT")
    stage=Path(tempfile.mkdtemp(prefix="ingest-",dir=ROOT))
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or len(names)>10001: raise ValueError("INVALID_ARCHIVE")
        for info in z.infolist():
            if info.filename!="manifest.json" and not re.fullmatch("[0-9a-f]{64}",info.filename): raise ValueError("INVALID_ENTRY")
            if info.file_size>100*1024*1024 or info.external_attr>>16 & 0o170000 == 0o120000: raise ValueError("INVALID_SIZE_OR_LINK")
            with z.open(info) as src,(stage/info.filename).open("xb") as dst: shutil.copyfileobj(src,dst)
    manifest=json.loads((stage/"manifest.json").read_text(encoding="utf8"))
    return ingest(settings.sqlite_path,ROOT,manifest,stage)

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["catalog","export","ingest","ack"]);p.add_argument("value");a=p.parse_args()
    if a.command=="catalog":
        with readonly(settings.sqlite_path) as c,state(ROOT) as s: result={"sites":sites(c,a.value),"root":str(ROOT),"known_hashes":[r[0] for r in s.execute("SELECT DISTINCT sha256 FROM copies")]}
    elif a.command=="export": result=export(a.value)
    elif a.command=="ingest": result=accept(a.value)
    else:
        payload=json.loads(Path(a.value).read_text(encoding="utf8"))
        with state(ROOT) as c:
            for r in payload["items"]:
                if not re.fullmatch(r"\d+-\d+-[0-9a-f]{64}",r["key"]) or r["key"].split("-")[-1]!=r["sha256"]: raise ValueError("INVALID_RECEIPT")
                c.execute("INSERT OR IGNORE INTO mirrors VALUES(?,?,?,?)",(r["key"],r["sha256"],r["relative_path"],now()))
            c.commit()
        result={"acknowledged":len(payload["items"])}
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__": main()
