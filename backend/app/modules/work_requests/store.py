"""Separate queue and private results. No operational-ledger writes or shell execution."""
import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager, closing
from pathlib import Path
from uuid import uuid4
from .artifact_validation import PDF_PREFIX,validate_pdf,pdf_name,validate_edited_copy
from . import source_generation

FINAL = {'COMPLETED', 'DECLINED', 'FAILED', 'NEEDS_INFO'}
MAX_BYTES = 16 * 1024 * 1024
MAX_ORIGINAL_BYTES = 32 * 1024 * 1024


class Conflict(Exception):
    pass


def plain(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        raise ValueError('INVALID_TEXT')
    return value.strip()


def safe_path(path):
    path = Path(path).absolute()
    for item in [path, *path.parents]:
        if item.exists() and (item.is_symlink() or getattr(item.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('REPARSE_PATH_FORBIDDEN')
    return path


class RequestStore:
    def __init__(self, root, clock=time.time):
        self.root = safe_path(root)
        self.database = self.root / 'requests.sqlite3'
        self.clock = clock

    def copy_from_legacy(self,legacy_root):
        """Explicit private-root migration. Never removes or rewrites the legacy copy."""
        legacy=safe_path(legacy_root);config=safe_path(legacy/'config.json')
        if not config.is_file()or json.loads(config.read_text(encoding='utf-8')).get('enabled')is not False:raise Conflict('REQUEST_MODULE_MUST_BE_OFF')
        if self.root.exists()and any(self.root.iterdir()):raise Conflict('PRIVATE_DESTINATION_NOT_EMPTY')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        if os.name=='posix':self.root.chmod(0o700)
        marker=safe_path(self.root/'migration-incomplete.json');marker.write_text('{"complete":false}',encoding='utf-8')
        source_db=safe_path(legacy/'requests.sqlite3')
        with closing(sqlite3.connect(source_db.as_uri()+'?mode=ro',uri=True))as source,closing(sqlite3.connect(self.database))as destination:
            source.backup(destination)
        with closing(sqlite3.connect(self.database))as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('PRIVATE_COPY_DATABASE_INVALID')
            rows=db.execute('SELECT id,bytes,sha256 FROM files').fetchall()
            counts={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]for table in ['requests','files','events']}
        results=safe_path(self.root/'results');results.mkdir(mode=0o700)
        for file_id,size,digest in rows:
            if not re.fullmatch(r'[0-9a-f]{32}',file_id):raise ValueError('EXACT_RESULT_ID_REQUIRED')
            original=safe_path(legacy/'results'/file_id);target=safe_path(results/file_id)
            value=original.read_bytes()
            if len(value)!=size or hashlib.sha256(value).hexdigest()!=digest:raise Conflict('LEGACY_RESULT_INTEGRITY_FAILED')
            with target.open('xb')as stream:
                if os.name=='posix':os.fchmod(stream.fileno(),0o600)
                stream.write(value);stream.flush();os.fsync(stream.fileno())
        (self.root/'config.json').write_bytes(config.read_bytes())
        if os.name=='posix':self.database.chmod(0o600);(self.root/'config.json').chmod(0o600)
        marker.unlink()
        return {'database_sha256':hashlib.sha256(self.database.read_bytes()).hexdigest(),'counts':counts,'verified_result_files':len(rows),'legacy_preserved':True,'module_remains_OFF':True}

    @contextmanager
    def connection(self):
        safe_path(self.root);safe_path(self.database)
        if not self.database.is_file():
            raise RuntimeError('REQUEST_STORE_NOT_INITIALIZED')
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            if db.execute('PRAGMA user_version').fetchone()[0]!=4:
                raise RuntimeError('EXPLICIT_REQUEST_STORE_UPGRADE_REQUIRED')
            yield db
        finally:
            db.close()

    def initialize(self):
        if self.database.exists():
            raise Conflict('STORE_ALREADY_EXISTS')
        self.root.mkdir(parents=True, exist_ok=True,mode=0o700)
        if os.name=='posix':self.root.chmod(0o700)
        db = sqlite3.connect(self.database)
        try:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE requests (
              id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, login_id TEXT NOT NULL,
              request_key TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
              kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
              scope_exempt INTEGER NOT NULL, status TEXT NOT NULL,
              reply TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL,
              lease_hash TEXT, lease_until REAL, result_sha256 TEXT, source_json TEXT, selection_id TEXT,
              review_phase TEXT NOT NULL DEFAULT 'NONE',review_version INTEGER NOT NULL DEFAULT 0,
              preview_file_id TEXT,prepare_owner_id INTEGER,prepare_owner_login TEXT,
              conversation_id TEXT REFERENCES requests(id),parent_request_id TEXT REFERENCES requests(id),
              UNIQUE(user_id,request_key));
            CREATE TABLE files (
              id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id),
              filename TEXT NOT NULL, bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
              audience TEXT NOT NULL DEFAULT 'REQUESTER');
            CREATE TABLE events (
              id INTEGER PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id),
              status TEXT NOT NULL, at REAL NOT NULL);
            CREATE TABLE worker_state (id INTEGER PRIMARY KEY CHECK(id=1), seen_at REAL NOT NULL, capabilities TEXT NOT NULL DEFAULT '[]');
            CREATE TABLE nas_selections (
              id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,login_id TEXT NOT NULL,
              source_json TEXT NOT NULL,expires_at REAL NOT NULL);
            CREATE TABLE release_events (
              id INTEGER PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests(id),
              action TEXT NOT NULL,actor_user_id INTEGER NOT NULL,actor_login_id TEXT NOT NULL,
              review_version INTEGER NOT NULL,file_id TEXT,file_sha256 TEXT,source_sha256 TEXT NOT NULL,at REAL NOT NULL);
            CREATE INDEX request_conversation_order ON requests(user_id,login_id,conversation_id,created_at);
            PRAGMA user_version=4;
            ''')
        finally:
            db.close()
        if os.name=='posix':self.database.chmod(0o600)

    def upgrade_v1(self):
        """Explicit OFF-only queue upgrade; importing/serving never migrates a database."""
        config=safe_path(self.root/'config.json')
        if config.is_file()and json.loads(config.read_text(encoding='utf-8'))['enabled']is not False:
            raise Conflict('REQUEST_MODULE_MUST_BE_OFF')
        safe_path(self.database)
        db=sqlite3.connect(self.database,timeout=10)
        try:
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if version==4:return {'changed':False}
            if version==3:
                db.close();return self.upgrade_v3()
            if version==2:
                db.close();return self.upgrade_v2()
            expected={'id','user_id','login_id','request_key','payload_sha256','kind','title','body','scope_exempt','status','reply','created_at','updated_at','lease_hash','lease_until','result_sha256'}
            if {r[1]for r in db.execute('PRAGMA table_info(requests)')}!=expected:
                raise ValueError('EXACT_OLD_REQUEST_SCHEMA_REQUIRED')
            db.execute('BEGIN IMMEDIATE')
            tables=['requests','files','events','worker_state']
            counts={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]for table in tables}
            folder=safe_path(self.root/'schema-backups');folder.mkdir(exist_ok=True)
            backup=safe_path(folder/('before-schema2-'+uuid4().hex+'.sqlite3'))
            # A separate reader can snapshot WAL while the migration owns the writer reservation.
            with closing(sqlite3.connect(self.database))as source,closing(sqlite3.connect(backup))as target:source.backup(target)
            backup_sha=hashlib.sha256(backup.read_bytes()).hexdigest()
            db.execute('ALTER TABLE requests ADD COLUMN source_json TEXT')
            db.execute('ALTER TABLE requests ADD COLUMN selection_id TEXT')
            db.execute("ALTER TABLE worker_state ADD COLUMN capabilities TEXT NOT NULL DEFAULT '[]'")
            db.execute('CREATE TABLE nas_selections(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,login_id TEXT NOT NULL,source_json TEXT NOT NULL,expires_at REAL NOT NULL)')
            db.execute('PRAGMA user_version=2')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or list(db.execute('PRAGMA foreign_key_check')):
                raise RuntimeError('UPGRADE_INTEGRITY_FAILED')
            if counts!={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]for table in tables}:
                raise RuntimeError('UPGRADE_RECORD_COUNT_CHANGED')
            db.commit()
            first={'changed':True,'backup_name':backup.name,'backup_sha256':backup_sha,'preserved_counts':counts}
            db.close();first['schema3']=self.upgrade_v2();return first
        except Exception:
            try:db.rollback()
            except sqlite3.ProgrammingError:pass
            raise
        finally:db.close()

    def upgrade_v2(self):
        """Keep prior completion and bytes; unapproved legacy NAS files become owner-only."""
        config=safe_path(self.root/'config.json')
        if config.is_file()and json.loads(config.read_text(encoding='utf-8'))['enabled']is not False:raise Conflict('REQUEST_MODULE_MUST_BE_OFF')
        db=sqlite3.connect(safe_path(self.database),timeout=10)
        try:
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if version==4:return {'changed':False}
            if version==3:
                db.close();return self.upgrade_v3()
            if version!=2:raise ValueError('EXACT_SCHEMA2_REQUIRED')
            db.execute('BEGIN IMMEDIATE')
            counts={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]for t in ['requests','files','events','worker_state','nas_selections']}
            folder=safe_path(self.root/'schema-backups');folder.mkdir(exist_ok=True);backup=folder/('before-schema3-'+uuid4().hex+'.sqlite3')
            with closing(sqlite3.connect(self.database))as source,closing(sqlite3.connect(backup))as target:source.backup(target)
            for declaration in ["review_phase TEXT NOT NULL DEFAULT 'NONE'","review_version INTEGER NOT NULL DEFAULT 0",'preview_file_id TEXT','prepare_owner_id INTEGER','prepare_owner_login TEXT']:
                db.execute('ALTER TABLE requests ADD COLUMN '+declaration)
            db.execute("ALTER TABLE files ADD COLUMN audience TEXT NOT NULL DEFAULT 'REQUESTER'")
            db.execute('CREATE TABLE release_events(id INTEGER PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests(id),action TEXT NOT NULL,actor_user_id INTEGER NOT NULL,actor_login_id TEXT NOT NULL,review_version INTEGER NOT NULL,file_id TEXT,file_sha256 TEXT,source_sha256 TEXT NOT NULL,at REAL NOT NULL)')
            db.execute("UPDATE requests SET review_phase='LEGACY_READY',preview_file_id=(SELECT id FROM files WHERE request_id=requests.id LIMIT 1) WHERE source_json IS NOT NULL AND status='COMPLETED'")
            db.execute("UPDATE files SET audience='OWNER_PREVIEW' WHERE request_id IN (SELECT id FROM requests WHERE review_phase='LEGACY_READY')")
            db.execute("UPDATE requests SET status='AWAITING_REVIEW',review_phase='WAITING_REVIEW' WHERE source_json IS NOT NULL AND status='QUEUED'")
            db.execute("UPDATE requests SET status='INTERRUPTED',review_phase='WAITING_REVIEW',lease_hash=NULL,lease_until=NULL WHERE source_json IS NOT NULL AND status='RUNNING'")
            if counts!={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]for t in counts}:raise RuntimeError('UPGRADE_RECORD_COUNT_CHANGED')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok'or list(db.execute('PRAGMA foreign_key_check')):raise RuntimeError('UPGRADE_INTEGRITY_FAILED')
            db.execute('PRAGMA user_version=3');db.commit()
            result={'changed':True,'backup_name':backup.name,'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'preserved_counts':counts,'legacy_originals_held_for_owner_review':True}
            db.close();result['schema4']=self.upgrade_v3();return result
        except Exception:
            db.rollback();raise
        finally:db.close()

    def _event(self, db, request_id, status):
        db.execute('INSERT INTO events(request_id,status,at) VALUES(?,?,?)', (request_id,status,self.clock()))

    def upgrade_v3(self):
        """Explicit OFF-only addition of conversation links; preserve all prior fields and files."""
        config=safe_path(self.root/'config.json')
        if not config.is_file()or json.loads(config.read_text(encoding='utf-8')).get('enabled')is not False:
            raise Conflict('REQUEST_MODULE_MUST_BE_OFF')
        with closing(sqlite3.connect(safe_path(self.database),timeout=10))as db:
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if version==4:return {'changed':False}
            if version!=3:raise ValueError('EXACT_SCHEMA3_REQUIRED')
            db.execute('BEGIN IMMEDIATE')
            tables=['requests','files','events','worker_state','nas_selections','release_events']
            before={t:db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall()for t in tables}
            columns=[r[1]for r in db.execute('PRAGMA table_info(requests)')]
            folder=safe_path(self.root/'schema-backups');folder.mkdir(exist_ok=True)
            backup=folder/('before-schema4-'+uuid4().hex+'.sqlite3')
            with closing(sqlite3.connect(self.database))as source,closing(sqlite3.connect(backup))as target:source.backup(target)
            try:
                db.execute('ALTER TABLE requests ADD COLUMN conversation_id TEXT REFERENCES requests(id)')
                db.execute('ALTER TABLE requests ADD COLUMN parent_request_id TEXT REFERENCES requests(id)')
                db.execute('UPDATE requests SET conversation_id=id')
                db.execute('CREATE INDEX request_conversation_order ON requests(user_id,login_id,conversation_id,created_at)')
                for table,rows in before.items():
                    selected=','.join('"'+c.replace('"','""')+'"'for c in columns)if table=='requests'else'*'
                    if db.execute('SELECT '+selected+' FROM '+table+' ORDER BY rowid').fetchall()!=rows:raise RuntimeError('PRIOR_CONVERSATION_ROWS_CHANGED')
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok'or list(db.execute('PRAGMA foreign_key_check')):raise RuntimeError('UPGRADE_INTEGRITY_FAILED')
                db.execute('PRAGMA user_version=4');db.commit()
            except Exception:db.rollback();raise
            return {'changed':True,'backup_name':backup.name,'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'prior_fields_preserved':True,'preserved_counts':{t:len(rows)for t,rows in before.items()}}

    def _expire(self, db):
        from .naver_delivery import expire as expire_delivery
        expire_delivery(db,self)
        rows = db.execute("SELECT id FROM requests WHERE status='RUNNING' AND lease_until<?",(self.clock(),)).fetchall()
        for row in rows:
            db.execute("UPDATE requests SET status='INTERRUPTED',lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",(self.clock(),row['id']))
            self._event(db,row['id'],'INTERRUPTED')

    def _public(self, db, row, owner=False):
        if row is None:
            raise KeyError('NOT_FOUND')
        result = {k:row[k] for k in ['id','kind','title','body','status','reply','created_at','updated_at']}
        # Progress is derived from the private existing event ledger, not a new schema.
        # Completed/cancelled requests never retain an in-progress message.
        progress=db.execute("SELECT status FROM events WHERE request_id=? ORDER BY id DESC LIMIT 1",(row['id'],)).fetchone() if row['status']=='RUNNING' else None
        from .source_choices import pending as pending_choices
        result['source_choices_available']=row['status']=='NEEDS_INFO'and bool(pending_choices(db,row['id']))
        result['processing_phase']=progress['status'].removeprefix('PROGRESS_') if progress and progress['status'] in {'PROGRESS_SMALL','PROGRESS_LARGE','PROGRESS_DOCUMENT_BUILDING','PROGRESS_SOURCE_READING'} else None
        result['files'] = [dict(r) for r in db.execute("SELECT id,filename,bytes,sha256 FROM files WHERE request_id=? AND (audience='REQUESTER' OR (? AND id=?))",(row['id'],int(owner),row['preview_file_id']))]
        from .input_images import for_request
        result['input_attachments']=for_request(db,row['id'])
        from .naver_delivery import for_request as delivery_for_request
        result['delivery']=delivery_for_request(db,row['id'])
        from .question_retry import retryable
        from .owner_source_choices import state as owner_choice_state
        result['owner_source_choices_available']=row['status']=='NEEDS_INFO'and owner_choice_state(db,row['id'])[0]is not None
        generation=source_generation.requested(db,row)
        result['can_retry']=retryable(row,result['delivery'],bool(result['files']),source_generation=generation is not None)
        result['source']=json.loads(row['source_json'])if row['source_json']else None
        result['review_phase']=row['review_phase'];result['review_version']=row['review_version']
        result['source_sha256']=self.source_digest(result['source'])if result['source']else None
        if generation:result['source_generation_format']=generation
        result['conversation_id']=row['conversation_id']or row['id'];result['parent_request_id']=row['parent_request_id']
        return result

    @staticmethod
    def source_digest(source):return hashlib.sha256(json.dumps(source,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def register_selection(self,actor,source):
        opaque=uuid4().hex+uuid4().hex
        with self.connection() as db,db:
            db.execute('DELETE FROM nas_selections WHERE expires_at<?',(self.clock(),))
            db.execute('INSERT INTO nas_selections VALUES(?,?,?,?,?)',(opaque,actor['id'],actor['login_id'],json.dumps(source,ensure_ascii=False,sort_keys=True),self.clock()+3600))
            db.execute('DELETE FROM nas_selections WHERE user_id=? AND id NOT IN (SELECT id FROM nas_selections WHERE user_id=? ORDER BY expires_at DESC,rowid DESC LIMIT 64)',(actor['id'],actor['id']))
        return opaque

    def selection(self,actor,opaque):
        if not isinstance(opaque,str)or not re.fullmatch(r'[0-9a-f]{64}',opaque):raise ValueError('INVALID_SELECTION')
        with self.connection() as db:
            row=db.execute('SELECT * FROM nas_selections WHERE id=? AND user_id=? AND login_id=? AND expires_at>=?',(opaque,actor['id'],actor['login_id'],self.clock())).fetchone()
        if row is None:raise KeyError('SELECTION_NOT_FOUND')
        return json.loads(row['source_json'])

    @staticmethod
    def payload_digest(kind,title,body,selection_id=None,parent_request_id=None,input_attachment_id=None,result_file_id=None):
        values=[kind,plain(title,100),plain(body,6000)]
        if selection_id is not None:values.append(selection_id)
        if parent_request_id is not None:values.append({'parent_request_id':parent_request_id})
        if input_attachment_id is not None:values.append({'input_attachment_id':input_attachment_id})
        if result_file_id is not None:values.append({'result_file_id':result_file_id})
        return hashlib.sha256(json.dumps(values,ensure_ascii=False).encode()).hexdigest()

    def replay(self,actor,request_key,kind,title,body,selection_id=None,parent_request_id=None,*,result_file_id=None):
        with self.connection() as db:
            old=db.execute('SELECT * FROM requests WHERE user_id=? AND request_key=?',(actor['id'],request_key)).fetchone()
            if old:
                if old['payload_sha256']!=self.payload_digest(kind,title,body,selection_id,parent_request_id,result_file_id=result_file_id)or old['login_id']!=actor['login_id']:raise Conflict('REQUEST_KEY_CONFLICT')
                return self._public(db,old)
        return None

    def create(self, actor, request_key, kind, title, body, source=None, selection_id=None,parent_request_id=None,*,completed_reply=None,input_attachment_id=None,delivery=None,result_followup_enabled=False,image_comparison_enabled=False,result_file_id=None):
        request_key=plain(request_key,80)
        if not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',request_key) or kind not in {'QUESTION','FILE','EDIT'}:
            raise ValueError('INVALID_REQUEST')
        title,body=plain(title,100),plain(body,6000)
        if (source is None)!=(selection_id is None):raise ValueError('INVALID_SOURCE_REQUEST')
        if kind=='EDIT'and(not source or source.get('extension')not in {'.txt','.docx','.xlsx'}):raise ValueError('SOURCE_EDIT_ORIGINAL_REQUIRED')
        if input_attachment_id is not None and(kind!='QUESTION'or source is not None or completed_reply is not None):raise ValueError('사진은 채팅 질문과 함께 보내 주세요.')
        from .naver_delivery import validate as validate_delivery
        validate_delivery(actor,delivery,kind,source,input_attachment_id,completed_reply)
        if result_file_id is not None:
            if not isinstance(result_file_id,str)or not re.fullmatch(r'[0-9a-f]{32}',result_file_id):raise ValueError('INVALID_RESULT_FILE')
            if not result_followup_enabled or not actor['owner']or kind!='QUESTION'or source is not None or selection_id is not None or input_attachment_id is not None or delivery is not None or completed_reply is not None:raise Conflict('RESULT_SELECTION_UNAVAILABLE')
        digest=self.payload_digest(kind,title,body,selection_id,parent_request_id,input_attachment_id,result_file_id)
        if delivery is not None:digest=hashlib.sha256((digest+'\0naver-delivery\0'+json.dumps(delivery,sort_keys=True)).encode()).hexdigest()
        if completed_reply is not None:
            if kind!='QUESTION' or source is not None:raise ValueError('INVALID_WEEKLY_NOTE')
            completed_reply=plain(completed_reply,3000)
            digest=hashlib.sha256((digest+'\0weekly-note\0'+completed_reply).encode()).hexdigest()
        with self.connection() as db, db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM requests WHERE user_id=? AND request_key=?',(actor['id'],request_key)).fetchone()
            if old:
                if old['payload_sha256']!=digest or old['login_id']!=actor['login_id']:raise Conflict('REQUEST_KEY_CONFLICT')
                return self._public(db,old)
            parent=None
            if parent_request_id is not None:
                if not isinstance(parent_request_id,str)or not re.fullmatch(r'[0-9a-f]{32}',parent_request_id):raise ValueError('INVALID_PARENT_REQUEST')
                parent=db.execute('SELECT * FROM requests WHERE id=? AND user_id=? AND login_id=?',(parent_request_id,actor['id'],actor['login_id'])).fetchone()
                if parent is None:raise KeyError('NOT_FOUND')
                if db.execute('SELECT 1 FROM requests WHERE parent_request_id=?',(parent_request_id,)).fetchone():raise Conflict('CONVERSATION_HAS_NEW_MESSAGE')
            if db.execute("SELECT COUNT(*) FROM requests WHERE user_id=? AND status IN ('QUEUED','RUNNING','AWAITING_REVIEW','AWAITING_RELEASE')",(actor['id'],)).fetchone()[0]>=10:
                raise Conflict('REQUEST_LIMIT_REACHED')
            rid=uuid4().hex;now=self.clock()
            phase='NONE'if not source else 'OWN'if actor['owner']else 'SHARED'if source.get('shared_file_id')and kind!='EDIT'else 'WAITING_REVIEW'
            status='AWAITING_REVIEW'if phase=='WAITING_REVIEW'else'QUEUED'
            db.execute('INSERT INTO requests(id,user_id,login_id,request_key,payload_sha256,kind,title,body,scope_exempt,status,created_at,updated_at,source_json,selection_id,review_phase,conversation_id,parent_request_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (rid,actor['id'],actor['login_id'],request_key,digest,kind,title,body,int(actor['owner']),status,now,now,json.dumps(source,ensure_ascii=False,sort_keys=True)if source else None,selection_id,phase,parent['conversation_id']if parent else rid,parent_request_id))
            if completed_reply is not None:
                status='COMPLETED'
                result_hash=hashlib.sha256(completed_reply.encode()).hexdigest()
                db.execute('UPDATE requests SET status=?,reply=?,result_sha256=? WHERE id=?',(status,completed_reply,result_hash,rid))
            from .input_images import bind
            bind(db,actor,input_attachment_id,rid)
            from .naver_delivery import bind as bind_delivery
            bind_delivery(db,self,delivery,rid)
            self._event(db,rid,status)
            if result_followup_enabled:
                from .result_followup import bind as bind_result
                from .grounding import file_name_question, current_text
                if result_file_id is not None or not (kind=='QUESTION' and file_name_question(current_text(body))):
                    bind_result(db,self,actor,rid,result_file_id)
            if image_comparison_enabled and kind=='QUESTION':
                from .image_comparison import inputs,needs_source
                from .result_followup import requested
                current=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
                if inputs(db,current)and(source is not None or needs_source(body)or requested(db,rid)):
                    self._event(db,rid,'IMAGE_COMPARISON_BOUND')
            return self._public(db,db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone())

    @staticmethod
    def _completion_token(row):
        return hashlib.sha256(json.dumps([row['id'],row['result_sha256'],row['reply'],row['updated_at']],separators=(',',':')).encode()).hexdigest()

    def _read_marker(self,actor,row):
        identity=hashlib.sha256(json.dumps([actor['id'],actor['login_id']],separators=(',',':')).encode()).hexdigest()
        return 'VIEWED:'+identity+':'+self._completion_token(row)

    def _read_state(self,db,actor,row,value):
        if row['status']=='COMPLETED':
            value['completion_token']=self._completion_token(row)
            value['unread']=db.execute('SELECT 1 FROM events WHERE request_id=? AND status=? LIMIT 1',(row['id'],self._read_marker(actor,row))).fetchone()is None
        return value

    def list(self, actor, before=None):
        with self.connection() as db, db:
            self._expire(db)
            clause='';values=[actor['id'],actor['login_id']]
            if before is not None:
                anchor=db.execute('SELECT created_at,id FROM requests WHERE id=? AND user_id=? AND login_id=?',(before,*values)).fetchone()
                if anchor is None:raise KeyError('NOT_FOUND')
                clause=' AND (created_at<? OR (created_at=? AND id<?))';values.extend([anchor['created_at'],anchor['created_at'],anchor['id']])
            rows=db.execute('SELECT * FROM requests WHERE user_id=? AND login_id=?'+clause+' ORDER BY created_at DESC,id DESC LIMIT 101',values).fetchall()
            total=db.execute('SELECT COUNT(*) FROM requests WHERE user_id=? AND login_id=?',(actor['id'],actor['login_id'])).fetchone()[0]
            more=len(rows)>100;rows=rows[:100]
            seen=db.execute('SELECT seen_at,capabilities FROM worker_state WHERE id=1').fetchone()
            online=bool(seen and self.clock()-seen[0]<90)
            return {'items':[self._read_state(db,actor,r,self._public(db,r,actor['owner'])) for r in rows],'total':total,'has_more':more,'next_cursor':rows[-1]['id']if more else None,'worker_online':online,'nas_worker_online':bool(online and 'NAS_REVIEW_V1'in json.loads(seen['capabilities'])),'edit_worker_online':bool(online and 'NAS_EDIT_V1'in json.loads(seen['capabilities'])),'pdf_worker_online':bool(online and 'GENERATED_PDF_V1'in json.loads(seen['capabilities']))}

    def conversations(self,actor,before=None):
        with self.connection()as db:
            rows=db.execute('SELECT conversation_id AS id,MAX(created_at) AS latest_at,COUNT(*) AS messages FROM requests WHERE user_id=? AND login_id=? GROUP BY conversation_id ORDER BY latest_at DESC,id DESC',(actor['id'],actor['login_id'])).fetchall()
            if before is not None:
                positions=[i for i,r in enumerate(rows)if r['id']==before]
                if not positions:raise KeyError('NOT_FOUND')
                rows=rows[positions[0]+1:]
            more=len(rows)>50;items=[]
            for row in rows[:50]:
                first=db.execute('SELECT title FROM requests WHERE id=?',(row['id'],)).fetchone()
                last=db.execute('SELECT id,status FROM requests WHERE conversation_id=? AND user_id=? AND login_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(row['id'],actor['id'],actor['login_id'])).fetchone()
                items.append({**dict(row),'title':first['title'],'last_request_id':last['id'],'status':last['status']})
            return {'items':items,'next_cursor':items[-1]['id']if more else None}

    def conversation(self,actor,rid,before=None):
        with self.connection()as db:
            row=db.execute('SELECT * FROM requests WHERE id=? AND user_id=? AND login_id=?',(rid,actor['id'],actor['login_id'])).fetchone()
            if row is None:raise KeyError('NOT_FOUND')
            values=[row['conversation_id'],actor['id'],actor['login_id']];clause=''
            if before is not None:
                anchor=db.execute('SELECT created_at,rowid FROM requests WHERE id=? AND conversation_id=? AND user_id=? AND login_id=?',(before,*values)).fetchone()
                if anchor is None:raise KeyError('NOT_FOUND')
                clause=' AND (created_at<? OR (created_at=? AND rowid<?))';values.extend([anchor['created_at'],anchor['created_at'],anchor['rowid']])
            rows=db.execute('SELECT * FROM requests WHERE conversation_id=? AND user_id=? AND login_id=?'+clause+' ORDER BY created_at DESC,rowid DESC LIMIT 101',values).fetchall()
            more=len(rows)>100;rows=rows[:100]
            return {'id':row['conversation_id'],'items':[self._read_state(db,actor,r,self._public(db,r,False))for r in reversed(rows)],'next_cursor':rows[-1]['id']if more else None}

    def conversation_file_names(self,actor,rid,visible,nas_metadata=None):
        """Requester-visible result metadata; never infer a name from chat text."""
        with self.connection()as db:
            row=db.execute('SELECT * FROM requests WHERE id=? AND user_id=? AND login_id=?',
                           (rid,actor['id'],actor['login_id'])).fetchone()
            if row is None:raise KeyError('NOT_FOUND')
            if row['kind']!='QUESTION' or not row['parent_request_id']:return []
            rows=db.execute("SELECT * FROM requests WHERE conversation_id=? AND user_id=? AND login_id=? AND rowid<(SELECT rowid FROM requests WHERE id=?) ORDER BY rowid DESC LIMIT 6",
                            (row['conversation_id'],actor['id'],actor['login_id'],rid)).fetchall()
            for prior in rows:
                if prior['status']!='COMPLETED':continue
                view=visible(self._public(db,prior,False),actor)
                names=[item['filename'] for item in view.get('files',[]) if isinstance(item.get('filename'),str)
                       and 0<len(item['filename'])<=255 and not any(c in item['filename']for c in '\x00\r\n/\\')]
                if names:return list(dict.fromkeys(names))[:5]
                if nas_metadata is not None and prior['kind']=='QUESTION' and not prior['source_json']:
                    from .grounding import recent_limit
                    limit=recent_limit(prior['body'])
                    if limit is not None:
                        # Revalidate the exact prior list with the current actor's
                        # authorized index. Chat prose never supplies a filename.
                        fresh=nas_metadata('recent',limit)
                        if fresh.get('status')!='COMPLETED' or fresh.get('reply')!=prior['reply']:return []
                        names=fresh.get('_file_names',[])
                        if not isinstance(names,list):return []
                        if any(not isinstance(n,str) or not 0<len(n)<=255 or any(c in n for c in '\x00\r\n/\\')for n in names):return []
                        return list(dict.fromkeys(names))[:10]
            return []

    def _conversation_body(self,db,row,validator):
        if not row['parent_request_id']:return row['body']
        rows=db.execute('SELECT * FROM requests WHERE conversation_id=? AND user_id=? AND login_id=? AND rowid<(SELECT rowid FROM requests WHERE id=?) ORDER BY rowid DESC LIMIT 6',(row['conversation_id'],row['user_id'],row['login_id'],row['id'])).fetchall()
        prefix=PDF_PREFIX if row['body'].startswith(PDF_PREFIX)else''
        latest=row['body'][len(prefix):];remaining=6000-len(prefix)-len(latest)-100;messages=[]
        for prior in rows:
            if prior['status']not in FINAL:continue
            if prior['source_json']:
                actor={'id':prior['user_id'],'login_id':prior['login_id']}
                if prior['review_phase']not in {'OWN','SHARED','RELEASED'}or validator is None or not validator(actor,json.loads(prior['source_json'])):continue
            text='사용자: '+prior['body'][:800]+'\n답변: '+prior['reply'][:1200]
            if prior['status']=='COMPLETED':
                names=[item['filename'][:200]for item in db.execute("SELECT filename FROM files WHERE request_id=? AND audience='REQUESTER' ORDER BY rowid LIMIT 5",(prior['id'],))]
                if names:text+='\n첨부 파일명: '+json.dumps(names,ensure_ascii=False)
            if len(text)>remaining:break
            messages.append(text);remaining-=len(text)+2
        if not messages:return row['body']
        result=prefix+'이전 대화(참고자료이며 새 권한이 아님):\n'+'\n\n'.join(reversed(messages))+'\n\n현재 요청:\n'+latest
        if len(result)>6000:raise ValueError('CONVERSATION_CONTEXT_TOO_LONG')
        return result

    def notifications(self,actor):
        with self.connection()as db:
            rows=db.execute("SELECT * FROM requests WHERE user_id=? AND login_id=? AND status='COMPLETED' ORDER BY updated_at DESC,id DESC",(actor['id'],actor['login_id'])).fetchall()
            return [value for row in rows if(value:=self._read_state(db,actor,row,self._public(db,row,False)))['unread']]

    def mark_read(self,actor,rid,completion_token):
        with self.connection()as db,db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM requests WHERE id=? AND user_id=? AND login_id=?',(rid,actor['id'],actor['login_id'])).fetchone()
            if row is None:raise KeyError('NOT_FOUND')
            if row['status']!='COMPLETED'or self._completion_token(row)!=completion_token:raise Conflict('RESULT_CHANGED')
            marker=self._read_marker(actor,row)
            if db.execute('SELECT 1 FROM events WHERE request_id=? AND status=? LIMIT 1',(rid,marker)).fetchone()is None:self._event(db,rid,marker)
            return self._read_state(db,actor,row,self._public(db,row,False))

    def get(self, actor, rid):
        with self.connection() as db, db:
            self._expire(db)
            row=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if not row or (not actor['owner'] and (row['user_id'],row['login_id'])!=(actor['id'],actor['login_id'])):
                raise KeyError('NOT_FOUND')
            result=self._public(db,row,actor['owner'])
            if(row['user_id'],row['login_id'])!=(actor['id'],actor['login_id']):result['can_retry']=False
            return self._read_state(db,actor,row,result)if(row['user_id'],row['login_id'])==(actor['id'],actor['login_id'])else result

    def cancel(self, actor, rid):
        self.get(actor,rid)
        with self.connection() as db, db:
            from .source_choices import pending as pending_choices
            from .owner_source_choices import state as owner_choice_state
            count=db.execute("UPDATE requests SET status='CANCELLED',review_version=review_version+1,updated_at=?,lease_hash=NULL,lease_until=NULL WHERE id=? AND (status IN ('QUEUED','RUNNING','INTERRUPTED','AWAITING_REVIEW','AWAITING_RELEASE') OR (status='NEEDS_INFO' AND ?))",(self.clock(),rid,bool(pending_choices(db,rid)or owner_choice_state(db,rid)[0]))).rowcount
            if not count:raise Conflict('REQUEST_ALREADY_FINISHED')
            self._event(db,rid,'CANCELLED')
        return self.get(actor,rid)

    def inbox(self):
        with self.connection()as db,db:
            self._expire(db)
            rows=db.execute("SELECT * FROM requests WHERE source_json IS NOT NULL AND review_phase NOT IN ('OWN','SHARED') ORDER BY created_at DESC LIMIT 100").fetchall()
            return [{**self._public(db,row,True),'_requester':{'id':row['user_id'],'login_id':row['login_id']}}for row in rows]

    @staticmethod
    def _owner(actor):
        if not actor.get('owner'):raise KeyError('OWNER_REQUIRED')

    def _review_row(self,db,rid,version,source_sha):
        row=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
        if row is None or not row['source_json']:raise KeyError('NAS_REQUEST_NOT_FOUND')
        if type(version)is not int or row['review_version']!=version or self.source_digest(json.loads(row['source_json']))!=source_sha:raise Conflict('REVIEW_CHANGED')
        return row

    @staticmethod
    def _review_access(row,actor,eligible,validator):
        pair=(row['user_id'],row['login_id']);allowed={(x['id'],x['login_id'])for x in eligible}
        source=json.loads(row['source_json'])
        if pair not in allowed or validator is None or not validator({'id':pair[0],'login_id':pair[1]},source)or not validator(actor,source):raise Conflict('REVIEW_ACCESS_CHANGED')

    def _release_event(self,db,row,action,actor,file=None):
        db.execute('INSERT INTO release_events(request_id,action,actor_user_id,actor_login_id,review_version,file_id,file_sha256,source_sha256,at) VALUES(?,?,?,?,?,?,?,?,?)',
            (row['id'],action,actor['id'],actor['login_id'],row['review_version'],file['id']if file else None,file['sha256']if file else None,self.source_digest(json.loads(row['source_json'])),self.clock()))

    def prepare_review(self,actor,rid,version,source_sha,eligible,validator):
        self._owner(actor)
        with self.connection()as db,db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if old and old['review_phase']in {'PREVIEW_QUEUED','PREVIEW_RUNNING'}and old['review_version']==version+1 and (old['prepare_owner_id'],old['prepare_owner_login'])==(actor['id'],actor['login_id'])and self.source_digest(json.loads(old['source_json']))==source_sha:return self._public(db,old,True)
            row=self._review_row(db,rid,version,source_sha)
            if row['status']not in {'AWAITING_REVIEW','NEEDS_INFO','INTERRUPTED'}or row['review_phase']in {'OWN','SHARED'}:raise Conflict('REVIEW_NOT_PREPARABLE')
            self._review_access(row,actor,eligible,validator)
            db.execute("UPDATE requests SET status='QUEUED',review_phase='PREVIEW_QUEUED',review_version=review_version+1,prepare_owner_id=?,prepare_owner_login=?,lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",(actor['id'],actor['login_id'],self.clock(),rid))
            fresh=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();self._release_event(db,fresh,'PREVIEW_REQUESTED',actor);self._event(db,rid,'QUEUED')
            return self._public(db,fresh,True)

    def release_original(self,actor,rid,version,source_sha,file_id,file_sha,eligible,validator):
        self._owner(actor)
        with self.connection()as db,db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if old and old['review_phase']=='RELEASED'and old['review_version']==version+1 and old['preview_file_id']==file_id:
                file=db.execute('SELECT * FROM files WHERE id=? AND request_id=?',(file_id,rid)).fetchone()
                if file and file['sha256']==file_sha and self.source_digest(json.loads(old['source_json']))==source_sha:return self._public(db,old,True)
            row=self._review_row(db,rid,version,source_sha)
            if row['review_phase']not in {'READY','LEGACY_READY'}or row['status']not in {'AWAITING_RELEASE','COMPLETED'}or row['preview_file_id']!=file_id:raise Conflict('EXACT_PREVIEW_REQUIRED')
            self._review_access(row,actor,eligible,validator)
            file=db.execute("SELECT * FROM files WHERE id=? AND request_id=? AND audience='OWNER_PREVIEW'",(file_id,rid)).fetchone()
            if file is None or file['sha256']!=file_sha:raise Conflict('PREVIEW_CHANGED')
            content=safe_path(self.root/'results'/file_id).read_bytes()
            if len(content)!=file['bytes']or hashlib.sha256(content).hexdigest()!=file_sha:raise Conflict('PREVIEW_INTEGRITY_FAILED')
            db.execute("UPDATE files SET audience='REQUESTER' WHERE id=?",(file_id,))
            db.execute("UPDATE requests SET status='COMPLETED',review_phase='RELEASED',review_version=review_version+1,reply=?,updated_at=?,lease_hash=NULL,lease_until=NULL WHERE id=?",(row['reply'] if row['kind']in {'QUESTION','EDIT'}or source_generation.requested(db,row) else '요청하신 자료입니다.',self.clock(),rid))
            fresh=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();self._release_event(db,fresh,'RELEASED',actor,file);self._event(db,rid,'COMPLETED')
            return self._public(db,fresh,True)

    def deny_original(self,actor,rid,version,source_sha,reason):
        self._owner(actor);reason=plain(reason,500)
        with self.connection()as db,db:
            db.execute('BEGIN IMMEDIATE');row=self._review_row(db,rid,version,source_sha)
            if row['review_phase']in {'OWN','SHARED','RELEASED','DENIED'}or row['status']in {'CANCELLED','ACCESS_REVOKED'}:raise Conflict('REVIEW_NOT_DENIABLE')
            status='COMPLETED'if row['status']=='COMPLETED'else'DECLINED'
            db.execute("UPDATE requests SET status=?,review_phase='DENIED',review_version=review_version+1,reply=?,updated_at=?,lease_hash=NULL,lease_until=NULL WHERE id=?",(status,reason,self.clock(),rid))
            fresh=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();self._release_event(db,fresh,'DENIED',actor);self._event(db,rid,status)
            return self._public(db,fresh,True)

    def claim(self, eligible, source_validator=None, capabilities=(), worker_actor=None,result_validator=None,*,image_comparison_enabled=False):
        # The server re-reads active user accounts and current module membership.
        # A previously recorded admin exemption cannot outlive that identity.
        eligible={(x['id'],x['login_id']):bool(x['owner']) for x in eligible}
        with self.connection() as db, db:
            db.execute('BEGIN IMMEDIATE');self._expire(db)
            db.execute('INSERT INTO worker_state(id,seen_at,capabilities) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET seen_at=excluded.seen_at,capabilities=excluded.capabilities',(self.clock(),json.dumps(list(capabilities))))
            row=None
            for candidate in db.execute("SELECT * FROM requests WHERE status='QUEUED' ORDER BY created_at,id").fetchall():
                from .naver_delivery import for_request as delivery_for_request
                if delivery_for_request(db,candidate['id'])is not None:continue
                if candidate['parent_request_id']:
                    parent=db.execute('SELECT status FROM requests WHERE id=?',(candidate['parent_request_id'],)).fetchone()
                    if parent and parent['status']in {'QUEUED','RUNNING','AWAITING_REVIEW','AWAITING_RELEASE'}:continue
                from .input_images import for_request
                comparison_bound=db.execute("SELECT 1 FROM events WHERE request_id=? AND status='IMAGE_COMPARISON_BOUND'",(candidate['id'],)).fetchone()
                if comparison_bound and(not image_comparison_enabled or 'UPLOADED_IMAGE_SOURCE_V1'not in capabilities):continue
                direct_images=for_request(db,candidate['id'])
                if direct_images and 'UPLOADED_IMAGE_V1'not in capabilities:continue
                if image_comparison_enabled:
                    from .image_comparison import inputs,CAP
                    contextual_images=inputs(db,candidate)
                    if contextual_images and CAP not in capabilities:continue
                elif candidate['source_json']and direct_images:continue
                if candidate['kind']=='EDIT'and 'NAS_EDIT_V1'not in capabilities:continue
                if candidate['kind']=='EDIT'and json.loads(candidate['source_json']).get('extension')=='.xlsx'and 'NAS_WORKBOOK_EDIT_V1'not in capabilities:continue
                if source_generation.requested(db,candidate)and 'NAS_SOURCE_CREATE_V1'not in capabilities:continue
                if candidate['kind']=='FILE'and not candidate['source_json']and candidate['body'].startswith(PDF_PREFIX)and 'GENERATED_PDF_V1'not in capabilities:continue
                pair=(candidate['user_id'],candidate['login_id'])
                if pair not in eligible:
                    db.execute("UPDATE requests SET status='ACCESS_REVOKED',updated_at=? WHERE id=?",(self.clock(),candidate['id']))
                    self._event(db,candidate['id'],'ACCESS_REVOKED')
                    continue
                from .result_followup import requested as result_requested,CAP as result_cap
                if result_requested(db,candidate['id']):
                    if result_cap not in capabilities:continue
                    try:
                        if result_validator is None or worker_actor is None:raise Conflict('RESULT_VALIDATOR_REQUIRED')
                        result_validator(db,candidate,worker_actor)
                    except Conflict:
                        db.execute("UPDATE requests SET status='ACCESS_REVOKED',lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",(self.clock(),candidate['id']));self._event(db,candidate['id'],'ACCESS_REVOKED');continue
                from .owner_source_choices import flow_started as owner_choice_flow
                if owner_choice_flow(db,candidate['id']):
                    if not eligible[pair]or worker_actor is None or pair!=(worker_actor['id'],worker_actor['login_id']):
                        db.execute("UPDATE requests SET status='ACCESS_REVOKED',updated_at=? WHERE id=?",(self.clock(),candidate['id']));self._event(db,candidate['id'],'ACCESS_REVOKED');continue
                    if not {'OWNER_SOURCE_CHOICES_V1','OWNER_SOURCE_CHOICES_V2'}&set(capabilities):continue
                if candidate['source_json']:
                    if 'NAS_REVIEW_V1'not in capabilities or worker_actor is None:continue
                    if candidate['review_phase']=='OWN'and not eligible[pair]:
                        db.execute("UPDATE requests SET status='AWAITING_REVIEW',review_phase='WAITING_REVIEW',review_version=review_version+1 WHERE id=?",(candidate['id'],));continue
                    if candidate['review_phase']=='PREVIEW_QUEUED'and (candidate['prepare_owner_id'],candidate['prepare_owner_login'])!=(worker_actor['id'],worker_actor['login_id']):
                        db.execute("UPDATE requests SET status='AWAITING_REVIEW',review_phase='WAITING_REVIEW',review_version=review_version+1 WHERE id=?",(candidate['id'],));continue
                    if candidate['review_phase']not in {'OWN','SHARED','PREVIEW_QUEUED'}:continue
                    actor={'id':candidate['user_id'],'login_id':candidate['login_id']}
                    if source_validator is None or not source_validator(actor,json.loads(candidate['source_json'])) or not source_validator(worker_actor,json.loads(candidate['source_json'])):
                        db.execute("UPDATE requests SET status='NEEDS_INFO',reply=?,updated_at=? WHERE id=?",('원본 자료와 이용 권한을 확인한 뒤 다시 선택해 주세요.',self.clock(),candidate['id']))
                        self._event(db,candidate['id'],'NEEDS_INFO');continue
                row=candidate;break
            if not row:return None
            token=uuid4().hex+uuid4().hex
            exempt=eligible[(row['user_id'],row['login_id'])]
            mode='OWNER_PREVIEW'if row['review_phase']=='PREVIEW_QUEUED'else'RESULT'
            db.execute("UPDATE requests SET status='RUNNING',lease_hash=?,lease_until=?,updated_at=?,scope_exempt=?,review_phase=CASE WHEN review_phase='PREVIEW_QUEUED' THEN 'PREVIEW_RUNNING' ELSE review_phase END WHERE id=?",(hashlib.sha256(token.encode()).hexdigest(),self.clock()+180,self.clock(),int(exempt),row['id']))
            self._event(db,row['id'],'RUNNING')
            return {**self._public(db,db.execute('SELECT * FROM requests WHERE id=?',(row['id'],)).fetchone(),True),'body':self._conversation_body(db,row,source_validator),'lease':token,'scope_exempt':exempt,'delivery_mode':mode,'_requester':{'id':row['user_id'],'login_id':row['login_id']}}

    def _lease(self, db, rid, lease):
        if not isinstance(lease,str) or not re.fullmatch(r'[0-9a-f]{64}',lease):raise Conflict('INVALID_LEASE')
        row=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
        digest=hashlib.sha256(lease.encode()).hexdigest()
        if not row or row['status']!='RUNNING' or row['lease_hash']!=digest or row['lease_until']<self.clock():
            raise Conflict('LEASE_NOT_CURRENT')
        return row

    def heartbeat(self, rid, lease, phase=None):
        if phase not in {None,'SMALL','LARGE','DOCUMENT_BUILDING','SOURCE_READING'}:raise ValueError('INVALID_PROCESSING_PHASE')
        with self.connection() as db, db:
            db.execute('BEGIN IMMEDIATE')
            self._lease(db,rid,lease)
            if phase is not None:
                prior=db.execute("SELECT status FROM events WHERE request_id=? ORDER BY id DESC LIMIT 1",(rid,)).fetchone()
                if prior is None or prior['status']!='PROGRESS_'+phase:self._event(db,rid,'PROGRESS_'+phase)
            db.execute('UPDATE requests SET lease_until=? WHERE id=?',(self.clock()+180,rid))
            db.execute('UPDATE worker_state SET seen_at=? WHERE id=1',(self.clock(),))

    def interrupt(self, rid, lease):
        with self.connection() as db, db:
            db.execute('BEGIN IMMEDIATE')
            self._lease(db,rid,lease)
            db.execute("UPDATE requests SET status='INTERRUPTED',lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",(self.clock(),rid))
            self._event(db,rid,'INTERRUPTED')
            return self._public(db,db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone())

    def finish(self, rid, lease, status, reply, business_allowed, eligible, filename=None, content=None, source_validator=None, delivery_mode='RESULT',worker_actor=None):
        if status not in FINAL or type(business_allowed) is not bool:raise ValueError('INVALID_RESULT')
        reply=plain(reply,12000)
        attachment=None
        if filename is not None or content is not None:
            if (not isinstance(filename,str) or not filename or len(filename)>255 or filename in {'.','..'}
                    or re.search(r'[\\/:*?"<>|\x00-\x1f]',filename)
                    or Path(filename).suffix.lower() not in {'.pdf','.docx','.xlsx','.pptx','.txt','.csv','.zip','.png','.jpg','.jpeg','.webp','.hwp','.hwpx','.xls'}
                    or not isinstance(content,bytes) or not 0<len(content)<=MAX_ORIGINAL_BYTES or status!='COMPLETED'):
                raise ValueError('INVALID_RESULT_FILE')
            attachment={'id':uuid4().hex,'filename':filename,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
        if delivery_mode not in {'RESULT','OWNER_PREVIEW'}:raise ValueError('INVALID_DELIVERY_MODE')
        signature_values=[status,reply,business_allowed,filename,attachment and attachment['sha256']]
        if delivery_mode!='RESULT':signature_values.append(delivery_mode)
        signature=hashlib.sha256(json.dumps(signature_values,ensure_ascii=False).encode()).hexdigest()
        with self.connection() as db, db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if old and old['status'] in FINAL|{'AWAITING_RELEASE'} and old['result_sha256']==signature and old['lease_hash']==hashlib.sha256(lease.encode()).hexdigest():
                return self._public(db,old,True)
            row=self._lease(db,rid,lease)
            current={(x['id'],x['login_id']):bool(x['owner']) for x in eligible}
            pair=(row['user_id'],row['login_id'])
            if pair not in current:raise Conflict('REQUESTER_ACCESS_REVOKED')
            if not current[pair] and not business_allowed and status not in {'DECLINED','FAILED','NEEDS_INFO'}:
                raise Conflict('BUSINESS_SCOPE_REQUIRED')
            if current[pair] and status=='DECLINED' and not business_allowed:
                raise Conflict('OWNER_SCOPE_EXEMPT')
            original_delivery=bool(row['source_json'] and row['kind']=='FILE' and not source_generation.requested(db,row))
            if attachment and len(content)>(MAX_ORIGINAL_BYTES if original_delivery else MAX_BYTES):raise ValueError('RESULT_SIZE_LIMIT')
            if attachment and len(content)>MAX_BYTES:
                import shutil
                if shutil.disk_usage(self.root).free<512*1024*1024:raise Conflict('RESULT_STORAGE_NOT_READY')
            if row['source_json']:
                source=json.loads(row['source_json'])
                if source_validator is None or worker_actor is None or not source_validator({'id':pair[0],'login_id':pair[1]},source)or not source_validator(worker_actor,source):raise Conflict('NAS_SOURCE_NO_LONGER_AVAILABLE')
                preview=row['review_phase']=='PREVIEW_RUNNING'
                if (delivery_mode=='OWNER_PREVIEW')!=preview:raise Conflict('DELIVERY_MODE_MISMATCH')
                if preview and (row['prepare_owner_id'],row['prepare_owner_login'])!=(worker_actor['id'],worker_actor['login_id']):raise Conflict('PREVIEW_OWNER_CHANGED')
                if not preview and row['review_phase']not in {'OWN','SHARED'}:raise Conflict('RELEASE_REQUIRED')
                if row['review_phase']=='OWN'and not current[pair]:raise Conflict('OWNER_SCOPE_CHANGED')
                generation=source_generation.requested(db,row)
                if status=='COMPLETED'and generation:
                    if not attachment or not business_allowed or not preview and not current[pair]:raise Conflict('SOURCE_GENERATION_PREVIEW_REQUIRED')
                    source_generation.validate(row['title'],generation,filename,content)
                    if source.get('approved_content_sha256')==attachment['sha256']:raise Conflict('GENERATED_COPY_REQUIRED')
                elif status=='COMPLETED'and row['kind']=='EDIT':
                    if not attachment or not business_allowed:raise Conflict('SOURCE_EDIT_COPY_REQUIRED')
                    validate_edited_copy(source['file_name'],filename,content)
                elif status=='COMPLETED':
                    if not attachment or filename!=source['file_name']or len(content)!=source['size']or not business_allowed:raise Conflict('ORIGINAL_NAS_FILE_REQUIRED')
                    if source.get('approved_content_sha256')and attachment['sha256']!=source['approved_content_sha256']:raise Conflict('SHARED_ORIGINAL_CHANGED')
            elif delivery_mode!='RESULT':raise Conflict('PREVIEW_REQUIRES_NAS_SOURCE')
            elif row['kind']=='FILE'and row['body'].startswith(PDF_PREFIX)and status=='COMPLETED':
                if not attachment or filename!=pdf_name(row['title']) or not business_allowed:raise Conflict('EXACT_GENERATED_PDF_REQUIRED')
                validate_pdf(content)
            if attachment:
                directory=safe_path(self.root/'results');directory.mkdir(exist_ok=True)
                file=safe_path(directory/attachment['id'])
                with file.open('xb') as stream:
                    if os.name=='posix':os.fchmod(stream.fileno(),0o600)
                    stream.write(content);stream.flush();os.fsync(stream.fileno())
                db.execute('INSERT INTO files(id,request_id,filename,bytes,sha256,audience) VALUES(?,?,?,?,?,?)',(attachment['id'],rid,filename,len(content),attachment['sha256'],'OWNER_PREVIEW'if delivery_mode=='OWNER_PREVIEW'else'REQUESTER'))
            if delivery_mode=='OWNER_PREVIEW'and status=='COMPLETED':
                status='AWAITING_RELEASE'
                if row['kind']not in {'QUESTION','EDIT'}and not source_generation.requested(db,row):reply='자료 제공 확인을 기다리고 있습니다.'
                db.execute("UPDATE requests SET review_phase='READY',review_version=review_version+1,preview_file_id=? WHERE id=?",(attachment['id'],rid))
            db.execute('UPDATE requests SET status=?,reply=?,updated_at=?,lease_until=NULL,result_sha256=? WHERE id=?',(status,reply,self.clock(),signature,rid))
            if delivery_mode=='OWNER_PREVIEW'and status=='AWAITING_RELEASE':self._release_event(db,db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone(),'PREVIEW_PREPARED',worker_actor,attachment)
            elif row['source_json']and status=='COMPLETED':self._release_event(db,db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone(),'OWNER_PRIVATE_DELIVERED'if row['review_phase']=='OWN'else'SHARED_DELIVERED',worker_actor,attachment)
            self._event(db,rid,status)
            db.execute('UPDATE worker_state SET seen_at=? WHERE id=1',(self.clock(),))
            return self._public(db,db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone(),True)

    def download_stream(self,actor,rid,fid):
        self.get(actor,rid)
        if not re.fullmatch(r'[0-9a-f]{32}',fid):raise KeyError('NOT_FOUND')
        with self.connection()as db:
            row=db.execute("SELECT * FROM files WHERE id=? AND request_id=? AND (audience='REQUESTER'OR ?)",(fid,rid,int(actor['owner']))).fetchone()
            if not row:raise KeyError('NOT_FOUND')
        if not 0<row['bytes']<=MAX_ORIGINAL_BYTES:raise Conflict('RESULT_SIZE_LIMIT')
        stream=safe_path(self.root/'results'/fid).open('rb')
        try:
            before=os.fstat(stream.fileno());digest=hashlib.sha256();size=0
            while chunk:=stream.read(1024*1024):
                size+=len(chunk)
                if size>row['bytes']:raise Conflict('RESULT_INTEGRITY_FAILED')
                digest.update(chunk)
            after=os.fstat(stream.fileno())
            if size!=row['bytes']or digest.hexdigest()!=row['sha256']or(before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise Conflict('RESULT_INTEGRITY_FAILED')
            stream.seek(0);return row['filename'],stream,row['bytes']
        except BaseException:
            stream.close();raise

    def download(self, actor, rid, fid):
        self.get(actor,rid)
        if not re.fullmatch(r'[0-9a-f]{32}',fid):raise KeyError('NOT_FOUND')
        with self.connection() as db:
            row=db.execute("SELECT * FROM files WHERE id=? AND request_id=? AND (audience='REQUESTER'OR ?)",(fid,rid,int(actor['owner']))).fetchone()
            if not row:raise KeyError('NOT_FOUND')
        path=safe_path(self.root/'results'/fid)
        data=path.read_bytes()
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise Conflict('RESULT_INTEGRITY_FAILED')
        return row['filename'],data
