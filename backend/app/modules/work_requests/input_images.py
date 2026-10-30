"""Private, request-bound image inputs. They never grant NAS access."""
import hashlib,io,json,os,re,unicodedata,warnings
from uuid import uuid4
from .store import Conflict,safe_path

MAX_IMAGE_BYTES=8*1024*1024
FORMATS={'JPEG':('.jpg','image/jpeg'),'PNG':('.png','image/png'),'WEBP':('.webp','image/webp')}

def ready(db):return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='input_images_v1'").fetchone()is not None

def upgrade(store):
    with store.connection()as db,db:
        db.execute('''CREATE TABLE IF NOT EXISTS input_images_v1(
          id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,login_id TEXT NOT NULL,upload_key TEXT NOT NULL,
          filename TEXT NOT NULL,extension TEXT NOT NULL,media_type TEXT NOT NULL,bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,
          created_at REAL NOT NULL,status TEXT NOT NULL,request_id TEXT REFERENCES requests(id),UNIQUE(user_id,upload_key))''')
    root=safe_path(store.root/'input-images');root.mkdir(mode=0o700,exist_ok=True)
    if os.name=='posix':root.chmod(0o700)

def metadata(row):return {k:row[k]for k in['id','filename','bytes','sha256','media_type']}

def for_request(db,rid):
    if not ready(db):return []
    return [metadata(r)for r in db.execute("SELECT * FROM input_images_v1 WHERE request_id=? AND status='BOUND'",(rid,))]

def available(store):
    with store.connection()as db:return ready(db)

def validate_image(raw):
    if not 0<len(raw)<=MAX_IMAGE_BYTES:raise ValueError('사진은 8MB 이하로 첨부해 주세요.')
    from PIL import Image
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw))as image:
                if image.format not in FORMATS or getattr(image,'n_frames',1)!=1 or image.width*image.height>40_000_000:raise ValueError('지원하지 않는 사진입니다.')
                extension,media=FORMATS[image.format];image.verify()
                return extension,media
    except Exception:raise ValueError('JPG·PNG·WEBP 사진을 첨부해 주세요.')from None

def register(store,actor,key,filename,raw):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',key):raise ValueError('INVALID_UPLOAD_KEY')
    extension,media=validate_image(raw);filename=unicodedata.normalize('NFC',str(filename or '사진')).replace('\\','/').rsplit('/',1)[-1]
    filename=re.sub(r'[\x00-\x1f<>:"|?*]','_',filename).strip(' .')[:110]or'사진'
    if '.'in filename:filename=filename.rsplit('.',1)[0]
    filename+=extension;digest=hashlib.sha256(raw).hexdigest();identity=uuid4().hex
    with store.connection()as db,db:
        db.execute('BEGIN IMMEDIATE')
        if not ready(db):raise RuntimeError('INPUT_IMAGES_NOT_INITIALIZED')
        existing=db.execute('SELECT * FROM input_images_v1 WHERE user_id=? AND upload_key=?',(actor['id'],key)).fetchone()
        if existing:
            if existing['login_id']!=actor['login_id']or existing['sha256']!=digest or existing['status']!='DRAFT':raise Conflict('UPLOAD_KEY_CONFLICT')
            return metadata(existing)
        if db.execute("SELECT COUNT(*) FROM input_images_v1 WHERE user_id=? AND status='DRAFT'",(actor['id'],)).fetchone()[0]>=20:raise Conflict('DRAFT_IMAGE_LIMIT')
        root=safe_path(store.root/'input-images');root.mkdir(exist_ok=True,mode=0o700);path=safe_path(root/(identity+extension))
        with path.open('xb')as stream:stream.write(raw)
        if os.name=='posix':path.chmod(0o600)
        db.execute('INSERT INTO input_images_v1 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(identity,actor['id'],actor['login_id'],key,filename,extension,media,len(raw),digest,store.clock(),'DRAFT',None))
        return metadata(db.execute('SELECT * FROM input_images_v1 WHERE id=?',(identity,)).fetchone())

def bind(db,actor,identity,rid):
    if identity is None:return
    if not ready(db):raise RuntimeError('INPUT_IMAGES_NOT_INITIALIZED')
    row=db.execute("SELECT * FROM input_images_v1 WHERE id=? AND user_id=? AND login_id=? AND status='DRAFT'",(identity,actor['id'],actor['login_id'])).fetchone()
    if row is None:raise KeyError('사진을 다시 확인해 주세요.')
    db.execute("UPDATE input_images_v1 SET status='BOUND',request_id=? WHERE id=?",(rid,identity))

def retire(store,actor,identity):
    with store.connection()as db,db:
        row=db.execute("SELECT * FROM input_images_v1 WHERE id=? AND user_id=? AND login_id=?",(identity,actor['id'],actor['login_id'])).fetchone()
        if row is None:raise KeyError('NOT_FOUND')
        if row['status']=='BOUND':raise Conflict('이미 전송한 사진은 대화 이력에 보존됩니다.')
        db.execute("UPDATE input_images_v1 SET status='REMOVED' WHERE id=?",(identity,))
    return {'removed':True}

def read(store,rid,identity,actor=None,lease=None,eligible=(),*,allow_context=False):
    with store.connection()as db:
        request=store._lease(db,rid,lease)if lease is not None else None
        if lease is not None and(request['user_id'],request['login_id'])not in {(u['id'],u['login_id'])for u in eligible}:raise KeyError('NOT_FOUND')
        if lease is None:store.get(actor,rid)
        origin=rid
        if allow_context:
            from .image_comparison import inputs
            current=request if request is not None else db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if current is None:raise KeyError('NOT_FOUND')
            candidates=[r for r in inputs(db,current)if r['id']==identity]
            if len(candidates)!=1:raise KeyError('NOT_FOUND')
            origin=candidates[0]['context_request_id']
        row=db.execute("SELECT * FROM input_images_v1 WHERE request_id=? AND id=? AND status='BOUND'",(origin,identity)).fetchone()
        if row is None:raise KeyError('NOT_FOUND')
        path=safe_path(store.root/'input-images'/(row['id']+row['extension']));raw=path.read_bytes()
        if len(raw)!=row['bytes']or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise Conflict('첨부 사진을 확인하지 못했습니다.')
        return metadata(row),raw
