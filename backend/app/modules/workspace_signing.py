"""Positioned PDF signing. Isolated storage; no changes to existing signature ledgers."""
import base64,hashlib,io,json,re,secrets,sqlite3,time
from contextlib import contextmanager
from pathlib import Path
from fastapi import APIRouter,Depends,File,Form,HTTPException,UploadFile
from fastapi.responses import JSONResponse,Response
from pydantic import BaseModel,Field,ConfigDict
from app.config.settings import settings

ROOT=Path(settings.storage_root)/'document-signing'
MAX_PDF=12*1024*1024
HEADERS={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'}
sha=lambda b:hashlib.sha256(b).hexdigest()

def enabled():
    p=Path(settings.storage_root)/'headquarters-workspace'/'workspace-feature-flags.json'
    if p.exists():
        try:
            if json.loads(p.read_text()).get('document_signing',True) is not True:raise HTTPException(503,'문서 서명 기능이 중지되어 있습니다.')
        except (ValueError,OSError):raise HTTPException(503,'문서 서명 설정을 확인해 주세요.')

@contextmanager
def store():
    enabled();ROOT.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(ROOT/'requests.sqlite3',timeout=15) as db:
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, owner INTEGER NOT NULL, name TEXT NOT NULL, signer TEXT NOT NULL, original_sha TEXT NOT NULL, pages TEXT NOT NULL, region TEXT, token_sha TEXT UNIQUE, expires INTEGER, status TEXT NOT NULL, created INTEGER NOT NULL, signed INTEGER, signature_sha TEXT, signed_sha TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id), action TEXT NOT NULL, actor INTEGER, at INTEGER NOT NULL)')
        try:yield db;db.commit()
        except BaseException:db.rollback();raise

def event(db,rid,action,actor=None):db.execute('INSERT INTO events(request_id,action,actor,at) VALUES(?,?,?,?)',(rid,action,actor,int(time.time())))
def packet(d):return JSONResponse(d,headers=HEADERS)
def info(row):
    return {k:row[k] for k in ('id','name','signer','original_sha','status','created','signed','signed_sha','expires')}|{'pages':json.loads(row['pages']),'region':json.loads(row['region']) if row['region'] else None,'expired':bool(row['expires'] and row['expires']<time.time())}
def own(db,rid,user):
    row=db.execute('SELECT * FROM requests WHERE id=? AND owner=?',(rid,user.id)).fetchone()
    if row is None:raise HTTPException(404,'문서를 찾을 수 없습니다.')
    return row
def capability(db,token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise HTTPException(404,'유효하지 않은 링크입니다.')
    row=db.execute('SELECT * FROM requests WHERE token_sha=?',(sha(token.encode()),)).fetchone()
    if row is None:raise HTTPException(404,'유효하지 않은 링크입니다.')
    if row['status']=='REVOKED' or not row['region'] or not row['expires'] or row['expires']<time.time():raise HTTPException(410,'종료되거나 만료된 링크입니다.')
    return row
def original(row):
    p=ROOT/row['id']/'original.pdf';data=p.read_bytes()
    if sha(data)!=row['original_sha']:raise HTTPException(409,'원본 문서 확인이 필요합니다.')
    return data
def open_pdf(data):
    import fitz
    try:
        doc=fitz.open(stream=data,filetype='pdf')
        if doc.needs_pass or not 1<=len(doc)<=30:raise ValueError()
        for page in doc:
            if not 30<=page.rect.width<=3000 or not 30<=page.rect.height<=3000:raise ValueError()
            if any(w.field_type==fitz.PDF_WIDGET_TYPE_SIGNATURE and w.field_value for w in (page.widgets() or [])):raise ValueError()
        return doc
    except Exception:raise HTTPException(400,'암호나 기존 전자서명이 없는 30쪽 이하 PDF를 선택해 주세요.')
def preview(row,index,signed=False):
    import fitz
    data=original(row)
    if signed and row['signed_sha']:
        data=(ROOT/row['id']/('signed-'+row['signed_sha']+'.pdf')).read_bytes()
        if sha(data)!=row['signed_sha']:raise HTTPException(409,'서명 문서 확인이 필요합니다.')
    with open_pdf(data) as doc:
        if not 0<=index<len(doc):raise HTTPException(404,'문서 쪽을 확인해 주세요.')
        page=doc[index];zoom=min(1.7,1400/max(page.rect.width,page.rect.height));return page.get_pixmap(matrix=fitz.Matrix(zoom,zoom),alpha=False).tobytes('png')

class Region(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    page:int=Field(ge=0,le=29)
    x:float=Field(ge=0,lt=1)
    y:float=Field(ge=0,lt=1)
    w:float=Field(ge=.015,le=1)
    h:float=Field(ge=.01,le=1)
class LinkBody(BaseModel):
    region:Region
    original_sha:str=Field(pattern=r'^[a-f0-9]{64}$')
class TokenBody(BaseModel):
    token:str=Field(min_length=43,max_length=43)
class SignBody(TokenBody):
    signature:str=Field(min_length=40,max_length=700000)
    original_sha:str=Field(pattern=r'^[a-f0-9]{64}$')

def ink_image(raw):
    from PIL import Image,ImageChops
    try:
        text=raw.removeprefix('data:image/png;base64,');data=base64.b64decode(text,validate=True)
        if not 32<=len(data)<=512000:raise ValueError()
        with Image.open(io.BytesIO(data)) as im:
            if im.format!='PNG' or not 10<=im.width<=2048 or not 10<=im.height<=2048:raise ValueError()
            im.load();rgba=im.convert('RGBA');white=Image.new('RGBA',im.size,'white');white.alpha_composite(rgba);rgb=white.convert('RGB');difference=ImageChops.difference(rgb,Image.new('RGB',rgb.size,'white')).convert('L');mask=difference.point(lambda v:255 if v>30 else 0);box=mask.getbbox()
            if not box or sum(mask.histogram()[1:])<20:raise ValueError()
            # White/tinted canvas pixels never cover existing text outside the ink.
            rgb.putalpha(mask);cropped=rgb.crop(box);out=io.BytesIO();cropped.save(out,format='PNG');return out.getvalue(),sha(data)
    except Exception:raise HTTPException(400,'서명을 그려 주세요.')

def install(parent,authorized):
    router=APIRouter(prefix='/document-signing',tags=['document-signing'])
    def admin(user=Depends(authorized)):
        if getattr(user.role,'value',user.role) not in {'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN'} or getattr(user,'ui_type','')!='HQ_SAFE':raise HTTPException(403,'안전보건실 계정으로 이용해 주세요.')
        enabled();return user
    @router.get('/requests')
    def listing(user=Depends(admin)):
        with store() as db:return packet({'items':[info(r) for r in db.execute('SELECT * FROM requests WHERE owner=? ORDER BY created DESC,id DESC LIMIT 100',(user.id,))]})
    @router.post('/requests')
    async def upload(file:UploadFile=File(...),signer:str=Form(...,min_length=1,max_length=80),user=Depends(admin)):
        data=await file.read(MAX_PDF+1)
        if len(data)>MAX_PDF or not file.filename or not file.filename.lower().endswith('.pdf') or not data.startswith(b'%PDF-'):raise HTTPException(400,'12MB 이하 PDF를 선택해 주세요.')
        with open_pdf(data) as doc:pages=[{'width':p.rect.width,'height':p.rect.height} for p in doc]
        name=re.sub(r'[\x00-\x1f\\/:*?"<>|]','_',file.filename)[:180];rid=secrets.token_hex(16);now=int(time.time())
        with store() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM requests WHERE owner=? AND created>?',(user.id,now-86400)).fetchone()[0]>=100:raise HTTPException(429,'오늘 등록 가능한 문서 수를 초과했습니다.')
            folder=ROOT/rid;folder.mkdir();(folder/'original.pdf').write_bytes(data)
            db.execute('INSERT INTO requests(id,owner,name,signer,original_sha,pages,status,created) VALUES(?,?,?,?,?,?,?,?)',(rid,user.id,name,signer.strip(),sha(data),json.dumps(pages),'DRAFT',now));event(db,rid,'UPLOADED',user.id);return packet(info(own(db,rid,user)))
    @router.get('/requests/{rid}/page/{index}')
    def page_admin(rid:str,index:int,user=Depends(admin)):
        with store() as db:return Response(preview(own(db,rid,user),index),media_type='image/png',headers=HEADERS)
    @router.post('/requests/{rid}/link')
    def link(rid:str,body:LinkBody,user=Depends(admin)):
        with store() as db:
            db.execute('BEGIN IMMEDIATE');row=own(db,rid,user);r=body.region
            if row['status'] not in {'DRAFT','PENDING'}:raise HTTPException(409,'서명이 끝나거나 종료된 문서입니다.')
            if row['original_sha']!=body.original_sha or r.page>=len(json.loads(row['pages'])) or r.x+r.w>1.000001 or r.y+r.h>1.000001:raise HTTPException(400,'서명 위치를 다시 선택해 주세요.')
            token=secrets.token_urlsafe(32);db.execute('UPDATE requests SET region=?,token_sha=?,expires=?,status=? WHERE id=?',(r.model_dump_json(),sha(token.encode()),int(time.time())+7*86400,'PENDING',rid));event(db,rid,'LINK_CREATED',user.id);return packet({'document':info(own(db,rid,user)),'sign_url':'https://www.besma.co.kr/document-sign.html#'+token})
    @router.post('/requests/{rid}/revoke')
    def revoke(rid:str,user=Depends(admin)):
        with store() as db:
            db.execute('BEGIN IMMEDIATE');own(db,rid,user);db.execute("UPDATE requests SET status='REVOKED' WHERE id=?",(rid,));event(db,rid,'REVOKED',user.id);return packet({'revoked':True})
    @router.get('/requests/{rid}/pdf')
    def download(rid:str,user=Depends(admin)):
        with store() as db:
            row=own(db,rid,user)
            if not row['signed_sha']:raise HTTPException(409,'아직 서명 전입니다.')
            return pdf_response(row)
    @router.post('/public/view')
    def view(body:TokenBody):
        with store() as db:return packet(info(capability(db,body.token)))
    @router.post('/public/page/{index}')
    def page_public(index:int,body:TokenBody):
        with store() as db:return Response(preview(capability(db,body.token),index,signed=True),media_type='image/png',headers=HEADERS)
    @router.post('/public/sign')
    def sign(body:SignBody):
        import fitz
        image,digest=ink_image(body.signature)
        with store() as db:
            db.execute('BEGIN IMMEDIATE');row=capability(db,body.token)
            if body.original_sha!=row['original_sha']:raise HTTPException(409,'확인한 문서가 달라졌습니다. 다시 열어 주세요.')
            if row['signed_sha']:
                if row['signature_sha']!=digest:raise HTTPException(409,'이미 서명한 문서입니다.')
                return packet(info(row))
            if row['status']!='PENDING':raise HTTPException(409,'서명할 수 없는 문서입니다.')
            region=json.loads(row['region'])
            with open_pdf(original(row)) as doc:
                page=doc[region['page']];r=page.rect;box=fitz.Rect(region['x']*r.width,region['y']*r.height,(region['x']+region['w'])*r.width,(region['y']+region['h'])*r.height)*page.derotation_matrix
                page.insert_image(box,stream=image,keep_proportion=True,overlay=True,rotate=page.rotation);output=doc.tobytes(garbage=3,deflate=True)
            # A failed DB commit leaves an immutable unused artifact, never a replaced original.
            path=ROOT/row['id']/('signed-'+sha(output)+'.pdf');path.write_bytes(output)
            db.execute("UPDATE requests SET status='SIGNED',signed=?,signature_sha=?,signed_sha=? WHERE id=?",(int(time.time()),digest,sha(output),row['id']));event(db,row['id'],'SIGNED');return packet(info(db.execute('SELECT * FROM requests WHERE id=?',(row['id'],)).fetchone()))
    def pdf_response(row):
        data=(ROOT/row['id']/('signed-'+row['signed_sha']+'.pdf')).read_bytes()
        if sha(data)!=row['signed_sha']:raise HTTPException(409,'서명 문서 확인이 필요합니다.')
        return Response(data,media_type='application/pdf',headers=HEADERS|{'Content-Disposition':'attachment; filename="signed-document.pdf"'})
    @router.post('/public/pdf')
    def public_pdf(body:TokenBody):
        with store() as db:
            row=capability(db,body.token)
            if not row['signed_sha']:raise HTTPException(409,'아직 서명 전입니다.')
            return pdf_response(row)
    parent.include_router(router)
