"""Explicit field-evaluation activity. Assessment saves alone never start it."""
from contextlib import closing
from pathlib import Path
import sqlite3,time,re

INSPECTORS=frozenset({96,521,523})
HEARTBEAT_TTL=90
SESSION_TTL=12*60*60

def _db(root,write=False):
    p=Path(root)/'evaluation-activity.sqlite3'
    if not write:
        if not p.exists():return None
        c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
    else:
        p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);c=sqlite3.connect(p,timeout=5);p.chmod(0o600)
        c.executescript('CREATE TABLE IF NOT EXISTS sessions(actor INTEGER PRIMARY KEY,plan TEXT,context TEXT,started REAL,ended REAL);CREATE TABLE IF NOT EXISTS devices(actor INTEGER,device TEXT,seen REAL,PRIMARY KEY(actor,device));')
    if write and 'phone_seen'not in {r[1]for r in c.execute('PRAGMA table_info(sessions)')}:
        try:c.execute('ALTER TABLE sessions ADD COLUMN phone_seen REAL');c.commit()
        except sqlite3.OperationalError:
            if 'phone_seen'not in {r[1]for r in c.execute('PRAGMA table_info(sessions)')}:raise
    if write and 'selection_started'not in {r[1]for r in c.execute('PRAGMA table_info(sessions)')}:
        try:c.execute('ALTER TABLE sessions ADD COLUMN selection_started INTEGER NOT NULL DEFAULT 0');c.commit()
        except sqlite3.OperationalError:
            if 'selection_started'not in {r[1]for r in c.execute('PRAGMA table_info(sessions)')}:raise
    c.row_factory=sqlite3.Row
    return c

def read(root,actor,now=None):
    now=time.time()if now is None else now;c=_db(root)
    if c is None:return None
    with closing(c):
        r=c.execute('SELECT s.*,MAX(d.seen) AS seen FROM sessions s LEFT JOIN devices d ON d.actor=s.actor WHERE s.actor=? GROUP BY s.actor',(actor,)).fetchone()
        if not r or r['ended']is not None or now-r['started']>SESSION_TTL:return None
        phone=r['seen']if 'selection_started'in r.keys()and r['selection_started']else r['phone_seen']if 'phone_seen'in r.keys()else None
        return {**dict(r),'seen':phone,'state':'WAITING_PHONE'if phone is None else'ACTIVE'if 0<=now-phone<=HEARTBEAT_TTL else'CHECK_REQUIRED'}

def change(root,actor,plan,context,action,device,now=None,surface='UNKNOWN',selection='LEGACY'):
    if actor not in INSPECTORS:raise ValueError('ACTIVITY_NOT_ALLOWED')
    if selection not in {'NEARBY','CONFIRMED','LEGACY'}:raise ValueError('ACTIVITY_INVALID')
    if surface not in {'PHONE','PC','UNKNOWN'}:raise ValueError('ACTIVITY_INVALID')
    if action not in {'START','HEARTBEAT','STOP'}or not re.fullmatch(r'[0-9a-f-]{36}',device):raise ValueError('ACTIVITY_INVALID')
    now=time.time()if now is None else now
    with closing(_db(root,True))as c:
        c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM sessions WHERE actor=?',(actor,)).fetchone()
        if action=='START':
            same=old and old['ended']is None and old['context']==context and now-old['started']<=SESSION_TTL
            if not same:c.execute('DELETE FROM devices WHERE actor=?',(actor,))
            phone=old['phone_seen']if same else None
            if old and not same:c.execute('UPDATE sessions SET selection_started=0 WHERE actor=?',(actor,))
            c.execute('INSERT INTO sessions(actor,plan,context,started,ended,phone_seen)VALUES(?,?,?,?,NULL,?)ON CONFLICT(actor)DO UPDATE SET plan=excluded.plan,context=excluded.context,started=excluded.started,ended=NULL,phone_seen=excluded.phone_seen',(actor,plan,context,old['started']if same else now,phone))
        elif not old or old['ended']is not None or old['context']!=context or now-old['started']>SESSION_TTL:
            c.rollback();return {'state':'IDLE','active':False}
        if action=='STOP':c.execute('UPDATE sessions SET ended=? WHERE actor=?',(now,actor))
        else:c.execute('INSERT INTO devices VALUES(?,?,?)ON CONFLICT(actor,device)DO UPDATE SET seen=excluded.seen',(actor,device,now))
        if action=='START'and selection in {'NEARBY','CONFIRMED'}:c.execute('UPDATE sessions SET selection_started=1 WHERE actor=?',(actor,))
        if action!='STOP'and surface=='PHONE':c.execute('UPDATE sessions SET phone_seen=? WHERE actor=?',(now,actor))
        c.commit()
    r=read(root,actor,now)
    return {'state':r['state']if r else'IDLE','active':r is not None,'last_seen':r['seen']if r else None}
