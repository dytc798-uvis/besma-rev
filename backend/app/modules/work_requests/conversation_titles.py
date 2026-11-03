"""Bounded, extractive conversation naming; no model, tool execution or chat edits.

The naming role reads only one authenticated owner's turns. Its derived title is
stored separately from immutable request titles, bodies, files and receipts.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import unicodedata

VERSION = 'context-title-v1'
MAX_TITLE = 44
TABLE = '''CREATE TABLE IF NOT EXISTS titles(
 owner_key TEXT NOT NULL,conversation_id TEXT NOT NULL,title TEXT NOT NULL,
 context_sha256 TEXT NOT NULL,engine TEXT NOT NULL,updated_at REAL NOT NULL,
 PRIMARY KEY(owner_key,conversation_id))'''
TOPICS = [
 ('반기 안전보건평가', r'반기\s*(?:평가|안전보건)|(?:하반기|상반기).*평가|4\s*종\s*평가|안전보건평가|중대재해처벌법.*평가'),
 ('위험성평가', r'위험성\s*평가|최초\s*평가|수시\s*평가|상시\s*평가'),
 ('현장 점검', r'현장.*점검|점검\s*(?:계획|일정|결과|실적)|법규\s*(?:평가|이행|점검)'),
 ('월간자료', r'월간\s*자료|취합\s*(?:자료|현황|대장)|의견\s*청취.*취합'),
 ('ERP 자료', r'\berp\b|출역\s*(?:일보|관리|인원)|월출역|작업\s*일보|현장\s*정보.*엑셀'),
 ('경영회의 자료', r'경영\s*회의|반기\s*보고|실적\s*보고|회의.*발표|회의록'),
 ('안전교육', r'안전\s*교육|법정\s*교육|화재\s*대피|대피\s*훈련|비상\s*훈련'),
 ('사고사례 전파', r'사고\s*사례|사고.*전파|재발\s*방지'),
 ('부적합 조치', r'부적합|시정\s*조치|개선\s*조치'),
 ('대화이력', r'대화\s*이력|대화.*제목|제목.*대화|이력.*제목'),
 ('베스마 채팅', r'채팅|대화.*맥락|이전.*대화'),
 ('자료 검색', r'(?:파일|자료|문서).*검색|검색.*(?:파일|자료)|최신.*파일|최근.*자료'),
 ('안전보건관리비', r'안전보건관리비|산업안전보건관리비|안전.*예산'),
]
ACK = re.compile(r'^(?:안녕|안녕하세요|네|예|응|그래|알겠어|알겠습니다|고마워|감사합니다|진행해|진행하자|계속해|좋아|해줘|그렇게\s*해|확인|맞아)[.!?\s]*$')


def clean(text):
    value = unicodedata.normalize('NFC', text or '')
    # Titles are visible in compact history lists. Do not expose contacts,
    # credentials, private paths or embedded links there.
    value = re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', ' ', value)
    value = re.sub(r'(?:[A-Za-z]:\\|\\\\)[^\n]+', ' ', value)
    value = re.sub(r'(?i)(?:password|passwd|token|secret|비밀번호|인증번호|주민번호)\s*[:=]\s*\S+', ' ', value)
    value = re.sub(r'(?<!\d)(?:01[016789][ -]?\d{3,4}[ -]?\d{4}|\d{6}[ -]?[1-4]\d{6})(?!\d)', ' ', value)
    value = re.sub(r'[\x00-\x1f<>`#*{}\[\]]+', ' ', value)
    return ' '.join(value.split())


def generate(turns):
    """Name the main subject across turns, retaining a brief follow-up's context."""
    texts = [clean(t['body'])[:1500] for t in turns]
    texts = [t for t in texts if t and not ACK.fullmatch(t)]
    if not texts:
        return '새 대화'
    scores = []
    for order, (label, pattern) in enumerate(TOPICS):
        matches = [bool(re.search(pattern, t, re.I)) for t in texts]
        # Retain the original subject when a late correction is short, but let
        # a sustained new subject replace it. One acknowledgement cannot rename.
        score = sum(matches) + (1.25 if matches[0] else 0)
        first_match = re.search(pattern, texts[0], re.I)
        scores.append((score, -first_match.start() if first_match else -10000, -order, label))
    score, _, _, topic = max(scores)
    if score:
        joined = ' '.join(texts)
        if topic in {'반기 안전보건평가', '현장 점검'}:
            if re.search(r'제외.*(?:현장|사유)|(?:현장|사유).*제외', joined):
                suffix = '대상·제외현장 정리'
            elif re.search(r'일정|계획|배정|담당', joined):
                suffix = '계획·일정'
            elif re.search(r'증빙|사진|평가표|입력|작성', joined):
                suffix = '평가표·증빙'
            elif re.search(r'완료|진행중|미평가|현황|점수', joined):
                suffix = '진행현황'
            else:
                suffix = ''
        elif topic == '대화이력':
            suffix = '제목 자동 정리' if re.search(r'제목|저장', joined) else '맥락 유지'
        elif topic == 'ERP 자료':
            suffix = '정기 취합' if re.search(r'매일|매월|정기|자동|예약|07.?00|04.?00', joined) else '조회·확인'
        elif topic == '월간자료':
            suffix = '취합·평가 연계' if re.search(r'평가|증빙|연계', joined) else '취합현황'
        elif topic == '자료 검색':
            suffix = '최신본 확인' if re.search(r'최신|최근|수정일', joined) else ''
        else:
            suffix = ''
        title = topic + (' ' + suffix if suffix else '')
        # Add a site only when the conversation is consistently about one site.
        sites = set(re.findall(r'(?:청라\s*C18(?:BL)?|검단\s*101|강화\s*2(?:지역)?|고양\s*장항)', joined, re.I))
        if len(sites) == 1 and next(iter(sites)) in texts[0] and topic in {'반기 안전보건평가', '현장 점검', '위험성평가'}:
            title = next(iter(sites)) + ' ' + title
        return title[:MAX_TITLE].strip()
    # Extract a substantive request rather than using greetings or the opening
    # phrase. This fallback has no model connection and makes no semantic claims.
    candidates = [t for t in texts if not re.search(r'지시.*무시|시스템.*(?:지시|프롬프트)|비밀.*공개', t)]
    if not candidates:
        return '업무 문의'
    value = max(enumerate(candidates), key=lambda p: (len(set(re.findall(r'[가-힣A-Za-z]{2,}', p[1]))), -p[0]))[1]
    value = re.sub(r'^(?:안녕(?:하세요)?|저기|그리고|추가로)[,.!\s]*', '', value)
    value = re.sub(r'(?:해\s*주세요|해\s*줘|알려\s*주세요|알려\s*줘|해보자|하자|해라|한다|인가요|할까|있나요)[.!?\s]*$', '', value).strip()
    if len(value) > MAX_TITLE:
        value = value[:MAX_TITLE].rsplit(' ', 1)[0] or value[:MAX_TITLE]
    return value or '업무 문의'


def owner_key(actor):
    return hashlib.sha256(json.dumps([actor['id'], actor['login_id']], separators=(',', ':')).encode()).hexdigest()


def initialize(root):
    """Explicit deployment setup; do not migrate the existing request queue."""
    path = Path(root) / 'conversation-titles.sqlite3'
    if path.is_symlink():
        raise ValueError('REPARSE_PATH_FORBIDDEN')
    with closing(sqlite3.connect(path, timeout=5)) as db:
        db.execute(TABLE)
        db.commit()
    if __import__('os').name == 'posix':
        path.chmod(0o600)
    return path


def resolve(db, root, actor, conversation_id, *, persist=False):
    root_row = db.execute('SELECT id FROM requests WHERE id=? AND conversation_id=? AND user_id=? AND login_id=?',
                          (conversation_id, conversation_id, actor['id'], actor['login_id'])).fetchone()
    if root_row is None:
        raise KeyError('NOT_FOUND')
    params = (conversation_id, actor['id'], actor['login_id'])
    first = db.execute('SELECT rowid,id,body FROM requests WHERE conversation_id=? AND user_id=? AND login_id=? ORDER BY rowid LIMIT 4', params).fetchall()
    latest = db.execute('SELECT rowid,id,body FROM requests WHERE conversation_id=? AND user_id=? AND login_id=? ORDER BY rowid DESC LIMIT 28', params).fetchall()
    turns = sorted({r['id']: dict(r) for r in [*first, *latest]}.values(), key=lambda r: r['rowid'])
    fingerprint = hashlib.sha256(json.dumps([VERSION, turns], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    key = owner_key(actor)
    path = Path(root) / 'conversation-titles.sqlite3'
    title = None
    if path.is_file() and not path.is_symlink():
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)) as cache:
                row = cache.execute('SELECT title,context_sha256,engine FROM titles WHERE owner_key=? AND conversation_id=?', (key, conversation_id)).fetchone()
                if row and row[1] == fingerprint and row[2] == VERSION:
                    title = row[0]
        except sqlite3.Error:
            pass
    if title is None:
        title = generate(turns)
        if persist and path.is_file() and not path.is_symlink():
            try:
                with closing(sqlite3.connect(path, timeout=1)) as cache:
                    cache.execute('INSERT INTO titles VALUES(?,?,?,?,?,?) ON CONFLICT(owner_key,conversation_id)DO UPDATE SET title=excluded.title,context_sha256=excluded.context_sha256,engine=excluded.engine,updated_at=excluded.updated_at',
                                  (key, conversation_id, title, fingerprint, VERSION, time.time()))
                    cache.commit()
            except sqlite3.Error:
                pass  # Saving a derived title must never lose a chat message.
    return title


def refresh(db, root, rid):
    row = db.execute('SELECT user_id,login_id,conversation_id FROM requests WHERE id=?', (rid,)).fetchone()
    if row:
        resolve(db, root, {'id': row['user_id'], 'login_id': row['login_id']}, row['conversation_id'], persist=True)
