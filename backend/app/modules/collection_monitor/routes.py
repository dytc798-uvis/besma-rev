from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.core.auth import get_current_user
from app.config.settings import settings
from .core import GOV_CODES, VERSION, readonly, state, overview, now, is_evidence

router = APIRouter(prefix="/collection-monitor", tags=["collection-monitor"])
READ_ROLES={"HQ_SAFE","HQ_OTHER","HQ_SAFE_ADMIN","SUPER_ADMIN","ACCIDENT_ADMIN"}
WRITE_ROLES={"HQ_SAFE","HQ_SAFE_ADMIN","SUPER_ADMIN"}

def paths():
    return Path(settings.sqlite_path), Path(settings.storage_root) / "collection-monitor"

def hq(user=Depends(get_current_user)):
    if str(getattr(user.role,"value",user.role)) not in READ_ROLES:
        raise HTTPException(403,"HQ_ONLY")
    return user

def writer(user=Depends(hq)):
    if str(getattr(user.role,"value",user.role)) not in WRITE_ROLES:
        raise HTTPException(403,"READ_ONLY_ROLE")
    return user

@router.get("/context")
def context(user=Depends(get_current_user)):
    db,_ = paths()
    with readonly(db) as c:
        site = c.execute("SELECT site_code FROM sites WHERE id=?", (user.site_id,)).fetchone() if user.site_id else None
    role=str(getattr(user.role,"value",user.role))
    return {"version":VERSION,"role":role,"can_read_monitor":role in READ_ROLES,"can_manage":role in WRITE_ROLES,"site_id":user.site_id,"channel":"BESMA" if site and site[0] in GOV_CODES else "NAVERWORKS",
      "gov_site_codes":sorted(GOV_CODES),"artifact_menu_required":False}

@router.get("/overview")
def dashboard(month: str=Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$"),user=Depends(hq)):
    return overview(*paths(),month)

@router.get("/unmapped")
def unmapped(month: str=Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$"), user=Depends(writer)):
    _,root=paths()
    with state(root) as c:
        return {"items":[dict(r) for r in c.execute("SELECT * FROM copies WHERE month=? AND (site_id IS NULL OR period='') AND id IN (SELECT copy_id FROM scan_items WHERE scan_id=(SELECT MAX(id) FROM scans WHERE month=?)) ORDER BY relative_path LIMIT 500",(month,month)) if is_evidence(r)]}

class Classification(BaseModel):
    site_id:int=Field(gt=0)
    period:str=Field(pattern=r"^(20\d{2}-(0[1-9]|1[0-2])(-W[1-6])?)$")

@router.post("/copies/{copy_id}/classify")
def classify(copy_id:str, body:Classification,user=Depends(writer)):
    db,root=paths()
    with readonly(db) as main, state(root) as c:
        site=main.execute("SELECT site_code FROM sites WHERE id=?",(body.site_id,)).fetchone()
        old=c.execute("SELECT * FROM copies WHERE id=?",(copy_id,)).fetchone()
        if not site or not old: raise HTTPException(404,"NOT_FOUND")
        if not body.period.startswith(old["month"]): raise HTTPException(409,"PERIOD_MISMATCH")
        if old["category"]=="nonconformity" and "-W" not in body.period: raise HTTPException(422,"WEEK_REQUIRED")
        c.execute("UPDATE copies SET site_id=?,period=?,classified_by=?,classified_at=? WHERE id=?",(body.site_id,body.period,user.id,now(),copy_id))
        c.execute("INSERT INTO audit(actor_id,action,copy_id,before_json,after_json,occurred_at) VALUES(?,?,?,?,?,?)",(user.id,"CLASSIFY",copy_id,json_dump(dict(old)),body.model_dump_json(),now()))
        c.commit()
    return {"ok":True}

def json_dump(obj):
    import json
    return json.dumps(obj,ensure_ascii=False)

@router.get("/copies/{copy_id}/content")
def content(copy_id:str,user=Depends(writer)):
    _,root=paths()
    with state(root) as c:
        r=c.execute("SELECT filename,sha256 FROM copies WHERE id=?",(copy_id,)).fetchone()
    if not r: raise HTTPException(404,"NOT_FOUND")
    import hashlib
    p=root/"objects"/r["sha256"]
    if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=r["sha256"]:raise HTTPException(409,"CONTENT_HASH_MISMATCH")
    return FileResponse(p,filename=r["filename"],headers={"Cache-Control":"no-store"})
