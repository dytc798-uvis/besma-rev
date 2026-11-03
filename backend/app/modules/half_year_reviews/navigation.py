"""Short-lived, owner-scoped screen positions, separate from assessment records."""
from contextlib import closing
from pathlib import Path
import json, sqlite3, time
from .catalog import FORMS

TTL = 4 * 60 * 60

def validate(position, data):
    form = position['form']
    schema = FORMS[form]
    if position['criterion'] not in {q['id'] for q in schema['criteria']}:
        raise ValueError('NAVIGATION_INVALID')
    if schema.get('needs_subject'):
        if position['subject'] not in {p['id'] for p in data['subjects'][form]}:
            raise ValueError('SUBJECT_REQUIRED')
    elif position['subject'] != 'site':
        raise ValueError('NAVIGATION_INVALID')

def _value(row):
    return {'version': row['version'] if row else 0,
            'position': json.loads(row['position']) if row and time.time()-row['at'] < TTL else None}

def read(root, key, actor):
    path = Path(root) / 'navigation.sqlite3'
    if not path.exists():
        return _value(None)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=5)) as c:
        c.row_factory = sqlite3.Row
        return _value(c.execute('SELECT * FROM positions WHERE context=? AND actor=?', (key, actor)).fetchone())

def write(root, key, actor, position, expected, device, sequence):
    root = Path(root); root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / 'navigation.sqlite3'
    with closing(sqlite3.connect(path, timeout=5)) as c:
        path.chmod(0o600); c.row_factory = sqlite3.Row
        c.executescript('''CREATE TABLE IF NOT EXISTS positions(context TEXT,actor INTEGER,version INTEGER,position TEXT,at REAL,PRIMARY KEY(context,actor));
        CREATE TABLE IF NOT EXISTS devices(context TEXT,actor INTEGER,device TEXT,sequence INTEGER,PRIMARY KEY(context,actor,device));''')
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM positions WHERE context=? AND actor=?', (key, actor)).fetchone()
        old = c.execute('SELECT sequence FROM devices WHERE context=? AND actor=? AND device=?', (key, actor, device)).fetchone()
        value = _value(row)
        if old and sequence <= old['sequence'] or expected != value['version']:
            c.rollback(); return {**value, 'accepted': False}
        position = {**position, 'device': device}
        c.execute('INSERT OR REPLACE INTO positions VALUES(?,?,?,?,?)', (key, actor, value['version']+1, json.dumps(position), time.time()))
        c.execute('INSERT OR REPLACE INTO devices VALUES(?,?,?,?)', (key, actor, device, sequence))
        c.commit()
        return {'version': value['version']+1, 'position': position, 'accepted': True}
