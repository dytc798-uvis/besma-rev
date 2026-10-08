from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from app.core.auth import get_current_user
from app.core.government_workspace_access import government_actor, is_government_owner
from app.config.settings import settings
from .core import GOV_CODES, VERSION, readonly, state, scoped_overview, now, is_evidence
from .report import make_report
from .nas_export import public_plan, content_for, export_items
from urllib.parse import quote
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

router = APIRouter(prefix="/collection-monitor", tags=["collection-monitor"])
READ_ROLES={"HQ_SAFE","HQ_OTHER","HQ_SAFE_ADMIN","SUPER_ADMIN","ACCIDENT_ADMIN"}
WRITE_ROLES={"HQ_SAFE","HQ_SAFE_ADMIN","SUPER_ADMIN"}

def paths():
    return Path(settings.sqlite_path), Path(settings.storage_root) / "collection-monitor"

def hq(user=Depends(government_actor)):
    if str(getattr(user.role,"value",user.role)) not in READ_ROLES:
        raise HTTPException(403,"HQ_ONLY")
    return user

def writer(user=Depends(hq)):
    if str(getattr(user.role,"value",user.role)) not in WRITE_ROLES and not is_government_owner(user):
        raise HTTPException(403,"READ_ONLY_ROLE")
    return user

from app.core.auth import DbDep
from .configuration import CollectionSetting,read_configuration,save_configuration,display_groups

@router.get('/settings')
def collection_settings(user=Depends(writer)):
    with readonly(paths()[0]) as main:return read_configuration(main)

@router.put('/settings')
def update_collection_settings(payload:CollectionSetting,db:DbDep,user=Depends(writer)):
    return save_configuration(db,payload,user.id)

@router.get('/site-configuration')
def site_configuration(user=Depends(government_actor)):
    role=str(getattr(user.role,'value',user.role))
    if role not in {'SITE','SITE_FUNCTIONAL_EVAL'} or not user.site_id:raise HTTPException(403,'SITE_ONLY')
    with readonly(paths()[0]) as main:
        site=main.execute('SELECT site_code FROM sites WHERE id=?',(user.site_id,)).fetchone()
        if not site or site['site_code'] not in GOV_CODES:raise HTTPException(403,'GOVERNMENT_SITE_ONLY')
        config=read_configuration(main)
        return {'revision':config['revision'],'groups':display_groups(config),'items':[{k:i[k] for k in ('code','title','frequency','group_id','order','priority')} for i in config['items'] if i['enabled'] and i['required']]}

@router.get("/context")
def context(user=Depends(government_actor)):
    db,_ = paths()
    with readonly(db) as c:
        site = c.execute("SELECT site_code FROM sites WHERE id=?", (user.site_id,)).fetchone() if user.site_id else None
    role=str(getattr(user.role,"value",user.role))
    return {"version":VERSION,"role":role,"can_read_monitor":role in READ_ROLES,"can_manage":role in WRITE_ROLES or is_government_owner(user),"site_id":user.site_id,"read_only":bool(getattr(user,'government_preview',False)),"channel":"BESMA" if site and site[0] in GOV_CODES else "NAVERWORKS",
      "gov_site_codes":sorted(GOV_CODES),"artifact_menu_required":False}

@router.get("/overview")
def dashboard(month: str=Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$"), scope:str=Query('government',pattern='^(government|other)$'), priority_only:bool=True,user=Depends(hq)):
    return scoped_overview(*paths(),month,scope,priority_only)


@router.get('/report.xlsx')
def report(month:str=Query(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),scope:str=Query('government',pattern='^(government|other)$'),priority_only:bool=True,team:str|None=None,q:str='',document_code:str|None=None,only_missing:bool=False,user=Depends(writer)):
    payload=scoped_overview(*paths(),month,scope,priority_only,team=team,query=q,document_code=document_code,only_missing=only_missing)
    label='관급공사' if scope=='government' else '기타현장'
    return Response(make_report(payload),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(f'{label}_문서취합현황_{month}.xlsx'),'Cache-Control':'no-store'})


@router.get('/nas-export')
def nas_plan(month:str=Query(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),user=Depends(writer)):
    return public_plan(month)


@router.get('/nas-files/{key}')
def nas_file(key:str,month:str=Query(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),user=Depends(writer)):
    row,content=content_for(month,key)
    return Response(content,media_type='application/octet-stream',headers={'Cache-Control':'no-store','Content-Disposition':"attachment; filename*=UTF-8''"+quote(row['relative_path'].rsplit('/',1)[1])})


@router.get('/nas-export.zip')
def nas_zip(month:str=Query(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$'),user=Depends(writer)):
    import hashlib
    rows,missing=export_items(month)
    if missing:raise HTTPException(409,'원본이 없는 문서가 있어 전체 내보내기를 완료할 수 없습니다.')
    if sum(r['size'] for r in rows)>500*1024*1024:raise HTTPException(413,'직접 NAS 저장을 사용하세요.')
    b=BytesIO()
    with ZipFile(b,'w',ZIP_DEFLATED) as z:
        for row in rows:
            content=row['path'].read_bytes()
            if hashlib.sha256(content).hexdigest()!=row['sha256']:raise HTTPException(409,'SOURCE_CHANGED')
            z.writestr(row['relative_path'],content)
    return Response(b.getvalue(),media_type='application/zip',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(f'관급공사_NAS저장_{month}.zip'),'Cache-Control':'no-store'})

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
