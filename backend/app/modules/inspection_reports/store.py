from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,re,sqlite3,uuid,zipfile,io
from .pptx_report import make_report,normalize_photo

class ReportConflict(ValueError):pass
class ReportStore:
    def __init__(self,root,template):self.root=Path(root);self.template=Path(template)
    def connect(self):
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        c=sqlite3.connect(self.root/'reports.sqlite3',timeout=15);c.row_factory=sqlite3.Row
        c.execute('''CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,plan_id TEXT NOT NULL,request_key TEXT NOT NULL,payload_sha256 TEXT NOT NULL,metadata TEXT NOT NULL,filename TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,photo_count INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(user_id,request_key))''');c.commit();return c
    def public(self,row,replayed=False):
        return {'id':row['id'],'plan_public_id':row['plan_id'],'filename':row['filename'],'sha256':row['sha256'],'bytes':row['size'],'photo_count':row['photo_count'],'created_at':row['created_at'],'replayed':replayed,'file_url':'/safety-features/inspection-reports/'+row['id']+'/file'}
    def save(self,user_id,plan_id,request_key,fields,photos):
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',request_key):raise ValueError('REQUEST_KEY_INVALID')
        if not 1<=len(photos)<=24:raise ValueError('PHOTO_COUNT_INVALID')
        normalized=[{**normalize_photo(raw),'caption':caption}for raw,caption in photos]
        canonical={'fields':fields,'photos':[{'source_sha256':hashlib.sha256(raw).hexdigest(),'caption':caption}for raw,caption in photos]}
        payload=json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(',',':'));digest=hashlib.sha256(payload.encode()).hexdigest()
        with closing(self.connect())as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT * FROM reports WHERE user_id=? AND request_key=?',(user_id,request_key)).fetchone()
            if old:
                if old['payload_sha256']!=digest or old['plan_id']!=plan_id:raise ReportConflict('REQUEST_CHANGED')
                c.rollback()
                self.file(user_id,old['id']);return self.public(old,True)
            result=make_report(self.template.read_bytes(),fields,normalized)
            with zipfile.ZipFile(io.BytesIO(result))as z:
                if z.testzip()is not None:raise ValueError('REPORT_INVALID')
            rid=uuid.uuid4().hex;folder=self.root/str(user_id);folder.mkdir(exist_ok=True,mode=0o700);target=folder/(rid+'.pptx')
            safe=re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',fields['site_name']).strip(' .')[:90]or'현장'
            filename='반기평가표_'+safe+'_'+fields['inspection_date'].replace('-','')+'.pptx';stamp=datetime.now(timezone.utc).isoformat()
            created=False
            try:
                with target.open('xb')as f:
                    created=True;f.write(result);f.flush()
                c.execute('INSERT INTO reports VALUES(?,?,?,?,?,?,?,?,?,?,?)',(rid,user_id,plan_id,request_key,digest,payload,filename,hashlib.sha256(result).hexdigest(),len(result),len(normalized),stamp));c.commit()
            except Exception:
                c.rollback()
                # Only this operation's new files; never remove an earlier report.
                if created:target.unlink(missing_ok=True)
                raise
            return self.public(c.execute('SELECT * FROM reports WHERE id=?',(rid,)).fetchone())
    def receipt(self,user_id,request_key):
        with closing(self.connect())as c:
            row=c.execute('SELECT * FROM reports WHERE user_id=? AND request_key=?',(user_id,request_key)).fetchone()
            if row is None:raise KeyError('NOT_FOUND')
            return self.public(row,True)
    def history(self,user_id,plan_id):
        with closing(self.connect())as c:return [self.public(r)for r in c.execute('SELECT * FROM reports WHERE user_id=? AND plan_id=? ORDER BY created_at DESC,id DESC LIMIT 30',(user_id,plan_id))]
    def file(self,user_id,rid):
        if not re.fullmatch(r'[a-f0-9]{32}',rid):raise KeyError('NOT_FOUND')
        with closing(self.connect())as c:
            row=c.execute('SELECT * FROM reports WHERE user_id=? AND id=?',(user_id,rid)).fetchone()
            if row is None:raise KeyError('NOT_FOUND')
            path=self.root/str(user_id)/(rid+'.pptx')
            if path.is_symlink():raise ValueError('REPORT_CHANGED')
            data=path.read_bytes()
            if len(data)!=row['size']or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('REPORT_CHANGED')
            return data,row['filename']
