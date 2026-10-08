"""BESMA <-> company monthly NAS copies, central Windows PC only.

Existing SSH key stays on E:. No credentials are embedded or printed.
Every NAS output is a verified versioned business document. State stays on D:.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

NAS=Path(r"Z:\4. 안전보건관리실\★월간 자료 취합")
STATE=Path(r"D:\JSI\safety-workbench\work\collection-monitor-sync")
KEY=r"E:\SecureKeys\ssh\besma-ncp-ed25519"
HOST="besma-admin@101.79.24.88"
BASE=["-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=15","-i",KEY]
REMOTE="cd /srv/besma/backend && /srv/besma/backend/.venv/bin/python -B -m app.modules.collection_monitor.worker_io"
CATS={"inspection":"1. 안전 점검","legal-training":"2. 법적교육(특별,정기 등)","risk":"3. 위험성평가","opinions":"4. 근로자 의견 청취","site-training":"5. 현장안전보건 교육","safety-cost":"6. 산업안전보건관리비","nonconformity":"7. 부적합관리대장 취합"}
ALLOWED={".pdf",".xlsx",".xls",".xlsm",".docx",".doc",".hwp",".hwpx",".pptx",".png",".jpg",".jpeg",".txt"}

def call(args):
    r=subprocess.run(args,capture_output=True,text=True,encoding="utf8",errors="replace",timeout=900)
    if r.returncode: raise RuntimeError("TRANSPORT_FAILED: "+r.stderr[-250:])
    return r.stdout

def remote(command,value):
    if not re.fullmatch(r"[A-Za-z0-9_./:-]+",value): raise ValueError("INVALID_REMOTE_ARGUMENT")
    return json.loads(call(["ssh",*BASE,HOST,"sudo -n -u besma bash -c '"+REMOTE+" "+command+" "+value+"'"]))

def norm(value): return re.sub(r"[^a-z0-9가-힣]","",value.lower())

def identify(relative,sites):
    # Only exact site codes or a complete distinctive site label auto-classify.
    codes=[s for s in sites if re.search(r"(?<!\d)"+re.escape(s["site_code"])+r"(?!\d)",relative)]
    if len(codes)==1: return codes[0]["id"]
    matches=[]
    n=norm(relative)
    aliases={"26042":["신길5동"],"26050":["청라","피크원","푸르지오"],"25001":["청라","스타필드","전기4공구"],"25002":["청라","스타필드","소방전기2공구"],"26041":["창원","스타필드","소방전기1공구"],"26008":["부천","괴안3D"],"26048":["시티오씨엘","8단지"],"25023":["평택브레인시티8BL"],"26033":["운정아이파크포레스트"],"25062":["성환","하수처리장"],"26056":["경산상방","1BL"],"25034":["판교","SG세계물산"]}
    exact=[s for s in sites if s['active'] and s['site_code'] in aliases and all(norm(a) in n for a in aliases[s['site_code']])]
    if len(exact)==1:return exact[0]['id']
    team=re.search(r"(?:^|/)([1-6])팀(?:/|$)",relative)
    for s in sites:
        if team and s["team"]!=team[1]+"팀": continue
        body=re.sub(r"^\[[^]]+\]","",s["site_name"])
        label=norm(body)
        if len(label)>=8 and label in n: matches.append(s)
    return matches[0]["id"] if len(matches)==1 else None

def scan(month,sites,stage,known_hashes=()):
    yy,mm=month.split("-"); pattern=re.compile(r"(?<!\d)(?:"+yy+"|"+yy[2:]+r")[.\-_ ]?"+mm+r"(?:월|(?=[^0-9]|$))")
    files=[];complete=[];errors=0
    for cat,folder in CATS.items():
        root=NAS/folder;cat_errors=0
        if not root.is_dir(): errors+=1;continue
        def onerror(e):
            nonlocal cat_errors
            cat_errors+=1
        for directory,dirs,names in os.walk(root,onerror=onerror,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(directory)/d).is_symlink() and not (Path(directory)/d).stat().st_file_attributes & 0x400 and d not in {"이전버전","백업","archive",".git"}]
            for name in names:
                p=Path(directory)/name;rel=p.relative_to(NAS).as_posix()
                if p.suffix.lower() not in ALLOWED or p.is_symlink() or p.stat().st_file_attributes & 0x400 or name.startswith("~$"): continue
                if any(word in name.lower() for word in ("원본","양식","template","password","token","인증서","주민","통장")): continue
                if not pattern.search(rel): continue
                # A filename explicitly referring to a different month is not this period's evidence.
                explicit=re.search(r"(?<!\d)(20\d{2}|\d{2})[.\-_년 ]+(0?[1-9]|1[0-2])(?:\s*월|[.\-_])",name)
                if explicit and (int(explicit[1][-2:])!=int(yy[-2:]) or int(explicit[2])!=int(mm)): continue
                month_only=re.search(r"(?<!\d)(0?[1-9]|1[0-2])월",name)
                if month_only and int(month_only[1])!=int(mm):continue
                if not 0<p.stat().st_size<=100*1024*1024: cat_errors+=1;continue
                before=(p.stat().st_size,p.stat().st_mtime_ns);data=p.read_bytes();after=(p.stat().st_size,p.stat().st_mtime_ns)
                if before!=after:cat_errors+=1;continue
                sha=hashlib.sha256(data).hexdigest()
                if sha not in known_hashes and not (stage/sha).exists():(stage/sha).write_bytes(data)
                week=re.search(r"([1-6])주차",rel)
                period=month+("-W"+week[1] if week else "") if cat=="nonconformity" else month
                if cat=="nonconformity" and not week: period=""
                team=re.search(r"(?:^|/)([1-6]팀|관급)(?:/|$)",rel)
                files.append({"relative_path":rel,"filename":name,"sha256":sha,"size":len(data),"category":cat,"period":period,"site_id":identify(rel,sites),"team":team[1] if team else None})
        if not cat_errors: complete.append(cat)
        errors+=cat_errors
    return {"month":month,"files":files,"complete_categories":complete,"error_count":errors}

def safe_destination(relative):
    parts=relative.split("/")
    if not parts or parts[0] not in CATS.values() or "관급" not in parts or any(p in {"",".",".."} or re.search(r'[\\:*?"<>|\x00-\x1f]',p) for p in parts): raise ValueError("INVALID_NAS_DESTINATION")
    dest=NAS.joinpath(*parts)
    if not dest.resolve().is_relative_to(NAS.resolve()): raise ValueError("NAS_ESCAPE")
    cursor=NAS
    for part in parts[:-1]:
        cursor=cursor/part
        if cursor.exists() and (cursor.is_symlink() or cursor.stat().st_file_attributes & 0x400): raise ValueError("NAS_REPARSE")
        if not cursor.exists():cursor.mkdir()
    return dest

def run(month):
    STATE.mkdir(parents=True,exist_ok=True)
    import msvcrt
    lock=(STATE/"worker.lock").open("a+b");lock.write(b"0");lock.flush();lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        if not NAS.is_dir(): raise RuntimeError("NAS_NOT_AVAILABLE")
        run=Path(tempfile.mkdtemp(prefix="sync-",dir=STATE))
        catalog=remote("catalog",month)
        (run/"catalog.json").write_text(json.dumps(catalog,ensure_ascii=False),encoding="utf8")
        manifest=scan(month,catalog["sites"],run,set(catalog["known_hashes"]))
        (run/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False),encoding="utf8")
        bundle=run/"incoming.zip"
        with zipfile.ZipFile(bundle,"x",zipfile.ZIP_DEFLATED) as z:
            for p in run.iterdir():
                if p.name=="manifest.json" or re.fullmatch("[0-9a-f]{64}",p.name):z.write(p,p.name)
        # Transport staging is private and imported by the existing service identity.
        ident=run.name.replace("-","")
        remote_path="/tmp/besma-collection-"+ident+".zip"
        call(["scp",*BASE,str(bundle),HOST+":"+remote_path])
        target=catalog["root"]+"/incoming-"+ident+".zip"
        call(["ssh",*BASE,HOST,"sudo -n install -o besma -g besma -m 0640 "+remote_path+" "+target])
        accepted=remote("ingest",target)
        outgoing=remote("export",month)
        local=run/"outgoing.zip";download_path="/tmp/besma-collection-"+ident+"-out.zip"
        call(["ssh",*BASE,HOST,"sudo -n install -o besma-admin -g besma-admin -m 0600 "+outgoing["bundle"]+" "+download_path])
        call(["scp",*BASE,HOST+":"+download_path,str(local)])
        acknowledged=[]
        with zipfile.ZipFile(local) as z:
            if z.testzip():raise ValueError("TRANSFER_CRC")
            for item in json.loads(z.read("manifest.json"))["items"]:
                data=z.read(item["key"])
                if len(data)!=item["size"] or hashlib.sha256(data).hexdigest()!=item["sha256"]:raise ValueError("TRANSFER_HASH")
                dest=safe_destination(item["relative_path"])
                if dest.exists():
                    if hashlib.sha256(dest.read_bytes()).hexdigest()!=item["sha256"]:raise ValueError("NAS_NAME_CONFLICT")
                else:
                    with dest.open("xb") as f:f.write(data);f.flush();os.fsync(f.fileno())
                if hashlib.sha256(dest.read_bytes()).hexdigest()!=item["sha256"]:raise ValueError("NAS_SAVED_HASH")
                acknowledged.append(item)
        ack=run/"ack.json";ack.write_text(json.dumps({"items":acknowledged},ensure_ascii=False),encoding="utf8")
        remote_ack="/tmp/besma-collection-"+ident+"-ack.json"
        call(["scp",*BASE,str(ack),HOST+":"+remote_ack]);ack_result=remote("ack",remote_ack)
        result={"month":month,"nas_files":len(manifest["files"]),"mapped":sum(x["site_id"] is not None and bool(x["period"]) for x in manifest["files"]),"unmapped":sum(x["site_id"] is None or not x["period"] for x in manifest["files"]),"errors":manifest["error_count"],"server":accepted,"mirrored":len(acknowledged),"ack":ack_result,"finished_at":datetime.now().astimezone().isoformat(),"run":str(run)}
        (STATE/"status.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
        print(json.dumps(result,ensure_ascii=False))
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--month",default=datetime.now().strftime("%Y-%m"));a=p.parse_args()
    try:run(a.month)
    except Exception as exc:
        STATE.mkdir(parents=True,exist_ok=True)
        (STATE/"failure.json").write_text(json.dumps({"month":a.month,"at":datetime.now().astimezone().isoformat(),"error":type(exc).__name__,"reason":str(exc)[-300:]},ensure_ascii=False),encoding="utf8")
        raise
