"""Page explanations bound to the unchanged private source row and preview bytes."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path


def row_sha(row):
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


@lru_cache(maxsize=2)
def _catalog(path, stamp):
    file = Path(path)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 2 * 1024 * 1024:
        return {}
    raw = json.loads(file.read_text(encoding='utf-8'), object_pairs_hook=_unique)
    if raw.get('version') != 1 or not isinstance(raw.get('items'), list) or len(raw['items']) > 1000:
        return {}
    entries = {}
    for entry in raw['items']:
        key = (entry['id'], entry['page'])
        if any(type(v) is not int for v in key) or key in entries:
            return {}
        entries[key] = entry
    return entries


def page_guide(data_path, data, ident, page):
    unavailable = {'available': False, 'id': ident, 'page': page}
    try:
        data_path = Path(data_path)
        file = data_path.parent / 'policy-page-guides.json'
        if file.is_symlink():
            return unavailable
        stat = file.stat()
        entry = _catalog(str(file), (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)).get((ident, page))
        if not entry:
            return unavailable
        rows = [r for r in data['policies'] if r.get('id') == ident]
        fresh = [r for r in json.loads(data_path.read_text(encoding='utf-8'), object_pairs_hook=_unique)['policies'] if r.get('id') == ident]
        if len(rows) != 1 or len(fresh) != 1 or any(row_sha(r) != entry['item_sha256'] for r in (rows[0], fresh[0])):
            return unavailable
        image = data_path.parent / 'policy-previews' / f'{ident}-{page}.jpg'
        size, digest = entry['size'], entry['page_sha256']
        if type(size) is not int or not 5 <= size <= 8 * 1024 * 1024 or not re.fullmatch('[0-9a-f]{64}', digest):
            return unavailable
        if image.is_symlink() or not image.is_file() or image.stat().st_size != size:
            return unavailable
        with image.open('rb') as stream:
            payload = stream.read(size + 1)
        if len(payload) != size or not payload.startswith(b'\xff\xd8\xff') or not payload.endswith(b'\xff\xd9') or hashlib.sha256(payload).hexdigest() != digest:
            return unavailable
        output = {k: entry[k] for k in ('heading', 'summary', 'actions', 'page_type', 'needs_confirmation', 'confirmation_note')}
        if not all(isinstance(output[k], str) and len(output[k]) <= 1800 for k in ('heading', 'summary', 'page_type', 'confirmation_note')):
            return unavailable
        if type(output['needs_confirmation']) is not bool or not isinstance(output['actions'], list) or not 1 <= len(output['actions']) <= 3 or any(not isinstance(a, str) or not 1 <= len(a) <= 800 for a in output['actions']):
            return unavailable
        return dict(output, available=True, id=ident, page=page, page_sha256=digest)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
        return unavailable
