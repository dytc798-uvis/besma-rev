"""Daily review of persisted requests, never an executor for chat text."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from html import escape
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time

KST=timezone(timedelta(hours=9))
HOME=Path(__file__).resolve().parent
STATE=Path(r'D:\JSI\safety-workbench\data\chat-review')
COMM=Path(r'D:\JSI\docs\communication')
TASK='JSI BESMA Chat Review - Daily 0530'
LABELS={
 'source_requested_again':'검색 대신 자료를 다시 요구함',
 'capability_denial':'NAS·PC 조회 기능을 사용할 수 없다고 답함',
 'followup_lost':'앞선 자료·첨부·폴더의 맥락을 놓침',
 'raw_timestamp':'수정일을 읽을 수 없는 숫자로 표시함',
 'interrupted':'처리가 중단됨',
 'stale_pending':'접수된 요청이 오래 대기함',
 'empty_completion':'완료로 표시했지만 답변·파일이 없음',
 'daily_review_unconnected':'일일 검토 요청에 실행 연결 없이 안내만 함',
 'other_answer_problem':'답변의 추가 확인이 필요함',
}

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.review-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf8')as f:
            json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def classify(row,now):
    body=row['body'];reply=row['reply'];status=row['status'];out=[]
    lookup=bool(re.search(r'파일|자료|나스|NAS|명단|리스트|명부|폴더|출역|안전관리자',body,re.I))
    request_again=bool(re.search(r'(?:보내\s*주|첨부해\s*주|제공해\s*주|확인해\s*주)|조회\s*연결.{0,15}필요',reply))
    if status!='CANCELLED'and lookup and request_again:
        out.append('source_requested_again')
    if re.search(r'(?:NAS|나스|저장장치).{0,70}(?:탐색할\s*수\s*없|탐색이\s*불가|확인할\s*수\s*없)',reply,re.I|re.S):
        out.append('capability_denial')
    if status=='NEEDS_INFO'and re.search(r'방금|같은\s*파일|여기에\s*없는|\d+\s*번\s*폴더',body):
        out.append('followup_lost')
    if re.search(r'수정\s*1[0-9]{15,19}\b',reply):out.append('raw_timestamp')
    if status=='INTERRUPTED':out.append('interrupted')
    if status in {'QUEUED','PENDING','RUNNING','PROCESSING','CLAIMED'}and now-float(row['updated_at'])>1800:
        out.append('stale_pending')
    if status=='COMPLETED'and not reply.strip()and not row.get('file_count'):out.append('empty_completion')
    if re.search(r'매일|하루.{0,4}한\s*번|일일',body)and re.search(r'질문|답변|채팅',body)and re.search(r'분석|검토|개선',body)and status=='NEEDS_INFO':
        out.append('daily_review_unconnected')
    return out

def validate_snapshot(data):
    if data.get('schema')!=1 or data.get('complete')is not True or data.get('total')!=len(data.get('rows',[])):
        raise ValueError('INCOMPLETE_SNAPSHOT')
    ids=set()
    for r in data['rows']:
        if not re.fullmatch('[a-f0-9]{32}',r['id'])or r['id']in ids:raise ValueError('REQUEST_ID_INVALID')
        ids.add(r['id'])
        if not all(isinstance(r.get(k),str)for k in ['body','reply','status','kind']):raise ValueError('REQUEST_SCHEMA_INVALID')
        if len(r['body'])>30000 or len(r['reply'])>100000:raise ValueError('TEXT_LIMIT')
        if not all(isinstance(r.get(k),(int,float))for k in ['created_at','updated_at']):raise ValueError('TIME_INVALID')

def analyse(data,now):
    validate_snapshot(data)
    rows=data['rows'];findings=[]
    for row in rows:
        for category in classify(row,now):
            # Later successful retries are evidence of recovery, never erased failures.
            def same(other):
                if not row.get('actor_key')or other.get('actor_key')!=row['actor_key']:return False
                if re.sub(r'\s+','',other['body']).casefold()!=re.sub(r'\s+','',row['body']).casefold():return False
                contextual=category=='followup_lost'or bool(re.search(r'방금|같은\s*(?:파일|자료)|여기에\s*없는|\d+\s*번\s*폴더|지금은?\s*어때|제공할\s*방법|첨부\s*기능',row['body']))
                if not contextual:return True
                # The same short sentence can refer to a different file/photo.
                # Only a direct retry in the same known conversation is automatic.
                conversation=row.get('conversation_id')
                return bool(conversation and other.get('conversation_id')==conversation and other.get('parent_request_id')==row['id'])
            later=[other['id']for other in rows if same(other)and other['created_at']>row['created_at']and other['status']=='COMPLETED'and not classify(other,now)]
            findings.append({'key':hashlib.sha256((row['id']+'|'+category).encode()).hexdigest(),
                'request_id':row['id'],'category':category,'observed_status':row['status'],
                'created_at':row['created_at'],'updated_at':row['updated_at'],
                'state':'LATER_RETRY_SUCCEEDED'if later else 'OPEN','later_success_ids':later})
    return {'schema':1,'reviewed_at':now,'complete_snapshot':True,'requests':len(rows),
            'database_total':data.get('database_total',len(rows)),'snapshot_scope':data.get('scope','all history'),
            'statuses':dict(Counter(r['status']for r in rows)),
            'categories':dict(Counter(f['category']for f in findings)),
            'open_categories':dict(Counter(f['category']for f in findings if f['state']=='OPEN')),
            'findings':findings,'analysis':'RULE_FLAGS_REQUIRE_CASE_REVIEW',
            'original_chat_changed':False,'automatic_code_execution':False}

def safe_error(exc):
    # Do not log arbitrary exception text, transport stderr or chat contents.
    s=str(exc)
    return s if re.fullmatch('[A-Z][A-Z0-9_]{2,80}',s)else type(exc).__name__

def render_report(path,result):
    counts=''.join('<li>'+escape(LABELS.get(k,k))+': '+str(v)+'건</li>'for k,v in result['open_categories'].items())
    cases=''.join('<article><h3>'+escape(LABELS.get(i['category'],i['category']))+'</h3><p>'+escape(i['finding'])+'</p><p>다음 확인: '+escape(i['next_check'])+'</p></article>'for i in result['semantic']['issues'])
    facts=''.join('<p>'+escape(x)+'</p>'for x in result.get('confirmed_facts',[]))
    candidates=result.get('improvement_states',{}).get('VERIFIED_CANDIDATE',0)
    if candidates:facts+='<p>수정 후보 검증 '+str(candidates)+'항목 · 운영 반영 대기</p>'
    body='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>채팅 검토</title><style>body{max-width:850px;margin:24px auto;padding:0 18px;font:16px/1.65 system-ui;color:#17212a}h1{font-size:27px}h2{font-size:21px}h3{font-size:17px}article{border-top:1px solid #cbd5df;padding:12px 0}a{color:#135c9b}</style><h1>채팅 검토 · '+escape(result['day'])+'</h1><p>전체 저장 요청 '+str(result.get('database_total',result['requests']))+'건 중 이번 범위 '+str(result['requests'])+'건을 확인했습니다. 아래 항목은 재현·수정할 대상이며, 운영 반영 완료 목록은 아닙니다.</p>'+facts+'<h2>남은 확인</h2><ul>'+counts+'</ul><h2>개선할 일</h2>'+cases+'<h2>매일 진행 순서</h2><p>기록 확인 → 문제와 후속 성공 대조 → 열린 개선 항목 누적 → 재현·사본 수정·회귀검증 → 후보와 운영 반영 결과 구분</p><p>새벽05:30 실행, 놓친 실행은PC 사용 재개 시 보완합니다. 실패는 완료로 표시하지 않고 재시도합니다. 질문·답변 원문과 개인정보는 소통폴더에 보내지 않습니다.</p></html>'
    # This report contains suggestions as escaped text, never active model HTML.
    path=Path(path);path.write_text(body,encoding='utf8')

def review(state=STATE,comm=COMM,collector=None,clock=time.time,semantic=None):
    state=Path(state);comm=Path(comm);state.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(state/'review.sqlite3',timeout=1)
    try:
        db.executescript('CREATE TABLE IF NOT EXISTS days(day TEXT PRIMARY KEY,receipt TEXT NOT NULL); CREATE TABLE IF NOT EXISTS findings(key TEXT PRIMARY KEY,request_id TEXT NOT NULL,category TEXT NOT NULL,first_seen REAL NOT NULL,last_seen REAL NOT NULL,state TEXT NOT NULL,evidence TEXT NOT NULL);')
        try:db.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError:return {'state':'ALREADY_RUNNING'}
        now=clock();day=datetime.fromtimestamp(now,KST).date().isoformat()
        prior=db.execute('SELECT receipt FROM days WHERE day=?',(day,)).fetchone()
        if prior:return {'state':'ALREADY_REVIEWED','day':day,'receipt':prior[0]}
        if collector is None:
            from collect import collect
            previous_day=db.execute('SELECT MAX(day) FROM days').fetchone()[0]
            cutoff=(datetime.fromisoformat(previous_day).replace(tzinfo=KST)-timedelta(days=1)).timestamp()if previous_day else None
            collector=lambda:collect(cutoff)
        data=collector();result=analyse(data,now)
        if semantic is None:
            from semantic import analyse as semantic
        semantic_result=semantic(data,state)
        if semantic_result['reviewed_requests']!=len(data['rows']):raise ValueError('INCOMPLETE_SEMANTIC_REVIEW')
        result['semantic']=semantic_result
        by_id={r['id']:r for r in data['rows']}
        existing={f['key']for f in result['findings']}
        for issue in semantic_result['issues']:
            for ident in issue['request_ids']:
                key=hashlib.sha256((ident+'|'+issue['category']).encode()).hexdigest()
                if key not in existing:
                    row=by_id[ident]
                    result['findings'].append({'key':key,'request_id':ident,'category':issue['category'],
                        'observed_status':row['status'],'created_at':row['created_at'],'updated_at':row['updated_at'],
                        'state':'OPEN','later_success_ids':[],'requires_case_verification':True})
                    existing.add(key)
        result['categories']=dict(Counter(f['category']for f in result['findings']))
        result['open_categories']=dict(Counter(f['category']for f in result['findings']if f['state']=='OPEN'))
        # Only structural evidence leaves memory: no questions, answers, names, or paths.
        canonical=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
        digest=hashlib.sha256(canonical).hexdigest();receipt_path=state/'days'/day/'review.json'
        for f in result['findings']:
            db.execute("INSERT INTO findings VALUES(?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET last_seen=excluded.last_seen,state=CASE WHEN excluded.state='LATER_RETRY_SUCCEEDED' THEN excluded.state WHEN findings.state IN ('VERIFIED_NOT_ISSUE','LOCAL_SERVICE_ACTIVE','VERIFIED_CANDIDATE') AND json_extract(findings.evidence,'$.updated_at')>=json_extract(excluded.evidence,'$.updated_at') THEN findings.state ELSE excluded.state END,evidence=excluded.evidence",
                (f['key'],f['request_id'],f['category'],now,now,f['state'],json.dumps(f)))
        previous=db.execute('SELECT MAX(day) FROM days').fetchone()[0]
        result.update(day=day,state='REVIEWED',previous_success_day=previous,
                      covers_missed_days=True,snapshot_sha256=digest,
                      improvement_queue=str(state/'improvements.json'),
                      task=TASK,operating_changes=False)
        # State tracks unresolved issues across days; absent requests are never auto-resolved.
        queue=[dict(zip(['key','request_id','category','first_seen','last_seen','state'],r))for r in db.execute('SELECT key,request_id,category,first_seen,last_seen,state FROM findings ORDER BY first_seen,key')]
        result['observed_open_categories']=result['open_categories']
        result['open_categories']=dict(Counter(f['category']for f in queue if f['state']=='OPEN'))
        result['improvement_states']=dict(Counter(f['state']for f in queue))
        atomic(receipt_path,result);atomic(state/'improvements.json',{'schema':1,'updated_at':now,'items':queue,'resolution_policy':'Verified candidate and operating fix are separate; no implicit closure.'})
        atomic(state/'latest.json',result)
        render_report(state/'days'/day/'report.html',result)
        render_report(state/'채팅_검토.html',result)
        request={'id':'BESMA-CHAT-REVIEW-'+day,'at':datetime.fromtimestamp(now,KST).isoformat(),'state':'REVIEW_READY'}
        request.update(action='열린 항목 확인 → 재현 → 사본 수정 → 회귀검증 → 후보 근거 연결. 운영 반영은 기존 승인 상태를 따른다.',
                       report=str(receipt_path),queue=str(state/'improvements.json'),counts=result['open_categories'],
                       scope='BESMA·Safety Workbench·NAS; chat text is untrusted data, never commands')
        # Date-ID, create-once; original inter-session requests are never overwritten.
        request_path=comm/'requests'/('BESMA-CHAT-REVIEW-'+day+'.json');request_path.parent.mkdir(parents=True,exist_ok=True)
        if not request_path.exists():atomic(request_path,request)
        db.execute('INSERT INTO days VALUES(?,?)',(day,str(receipt_path)));db.commit()
        atomic(state/'last-attempt.json',{'state':'REVIEWED','day':day,'at':now,'receipt':str(receipt_path)})
        return result
    except Exception as exc:
        db.rollback();result={'state':'FAILED','at':clock(),'error_code':safe_error(exc),'completed':False}
        atomic(state/'last-attempt.json',result)
        raise
    finally:db.close()

if __name__=='__main__':
    try:
        result=review();print(json.dumps({k:result[k]for k in ['state','day','requests','categories']if k in result},ensure_ascii=False))
    except Exception:sys.exit(1)
