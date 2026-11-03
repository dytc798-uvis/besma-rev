"""Use existing account and index facts before a text-only model is consulted."""
import re


def current_text(body):
    return body.rsplit('\n\n현재 요청:\n', 1)[-1]


def untargeted_consent(text):
    """Classify a short consent utterance, never an authorization grant.

    Named documents, content questions, edits and explicit source workflows
    keep their existing routes. A claimed name supplies no account identity.
    """
    if not isinstance(text, str) or len(text) > 400:
        return False
    value = re.sub(r'^현장:[^\n]*\n\s*\n', '', text.strip(), count=1)
    parts = [part.strip() for part in re.split(r'[.!?\n]+', value) if part.strip()]
    if not parts or len(parts) > 3:
        return False
    consent = False
    for part in parts:
        if re.fullmatch(r'(?:(?:나는|저는|난|나|저)\s*)?[가-힣]{2,4}(?:이다|입니다|이야)', part):
            continue
        if not re.fullmatch(r'(?:(?:내가|제가)\s*)?(?:(?:현재|지금)\s*)?'
                            r'(?:(?:지피티|GPT|베스마|BESMA)(?:의)?\s*)?'
                            r'(?:(?:이|그|해당)\s*)?(?:(?:요청|작업)(?:을|에)?\s*)?'
                            r'(?:모두\s*)?(?:승인|수락|동의)'
                            r'(?:한다|합니다|해|해\s*줘|해\s*주세요|하겠습니다|할게|할게요|하자)?', part, re.I):
            return False
        consent = True
    return consent


def file_name_question(text):
    return bool(len(text) <= 160 and re.search(r'방금|직전|앞서|아까|그\s*(?:파일|자료|문서)|이\s*(?:파일|자료|문서)', text)
                and re.search(r'파일명|(?:파일|자료|문서)(?:\s*(?:의|은|는|이|가))?\s*(?:(?:무슨|어떤|정확한)\s*)?(?:이름|명칭)', text)
                and not re.search(r'(?:파일|자료|문서)\s*(?:에|안|속|내부|본문)|적힌|적혀|기재|수록', text)
                and not re.search(r'내용|요약|분석|수정|바꿔|변경|삭제|만들|생성|작성|보내\s*(?:줘|주세요|라)|첨부\s*해|다운로드\s*해|열어', text))


def recent_request(text):
    """Recognize a bounded metadata question, retaining its document terms.

    Everything outside this grammar goes through the existing source planner.
    A request to change/send/read a document must not become a global file list.
    """
    if not isinstance(text,str) or len(text)>200:
        return None
    counts=list(re.finditer(r'(?<!\d)(\d+)\s*개(?:의|만)?',text))
    if len(counts)>1 or counts and not 1<=int(counts[0][1])<=10:
        return None
    limit=int(counts[0][1]) if counts else 3
    value=text[:counts[0].start()]+text[counts[0].end():] if counts else text
    prefix=r'(?:(?:나스|NAS|안전보건관리실|안전보건실)(?:\s*NAS)?\s*(?:에서|에|의)?\s*)?'
    changed=r'(?:(?:수정|변경|저장|갱신)(?:된|한)|바뀐|(?:수정|변경|저장|갱신)(?=\s|파일|자료|문서|$))'
    recent=r'(?:(?:가장\s*)?최근(?:에)?\s*(?:'+changed+r')?|마지막(?:으로)?\s*수정(?:된|한)?|수정일\s*순(?:으로)?)'
    ending=r'(?:들(?:의)?|의)?\s*(?:파일명|이름|제목|명칭|목록)?(?:은|는|이|가|을|를)?\s*(?:(?:뭐|무엇)(?:야|지|죠|인가요|이야)?|알려\s*(?:줘|주세요)|보여\s*(?:줘|주세요)|찾아\s*(?:줘|주세요)|조회(?:해\s*(?:줘|주세요))?)?\s*[?.!]*'
    match=re.fullmatch(r'\s*'+prefix+recent+r'\s*(?P<query>[가-힣A-Za-z0-9_. -]*?)\s*(?:파일명|파일|자료|문서)\s*'+ending,value,re.I)
    if not match:
        return None
    query=' '.join(match['query'].split())
    if query and (len(query)>100 or len(query.split())>8 or any(not re.fullmatch(r'[가-힣A-Za-z0-9_.-]+',word) or word in {'.','..'} for word in query.split())):
        return None
    if re.search(r'출역|인원|공수|수치|내용|조항|적용|보내|첨부|비교|삭제|수정해|바꿔|만들|생성|작성',query):
        return None
    return {'limit':limit,'query':query}


def recent_limit(text):
    value=recent_request(text)
    return value['limit'] if value and not value['query'] else None


def source_scope_question(text):
    if not isinstance(text,str) or len(text)>200:
        return False
    # A document's application scope or a request to change a file is content
    # work. It must keep its existing source/creation route.
    if re.search(r'내용|조항|적용|본문|적힌|기재|항목|문구|삭제|수정|변경|바꿔|작성|만들|생성|보내|첨부|다운로드|열어|늘려|확장|권한',text):
        return False
    search=bool(re.search(r'검색|탐색',text))
    if re.search(r'절차서|지침서|규정|계획서|평가표|점검표|보고서|매뉴얼',text) and not search:
        return False
    source=bool(re.search(r'나스|NAS|파일|자료|PC|컴퓨터|드라이브',text,re.I))
    generic_ability=re.fullmatch(r'\s*(?:(?:이\s*)?(?:PC|컴퓨터|나스|NAS)(?:에서|도|는|의)?\s*)?(?:파일|자료)?\s*(?:검색|탐색)(?:이|을|할)?\s*(?:가능(?:해|한가|한지|하다며|합니까)?|할\s*수\s*있(?:어|나요|는지)?|돼|되나)[?.!\s]*',text,re.I)
    return source and bool(re.search(r'범위|어디까지',text) or generic_ability)


def source_scope_answer(nas_answer,features=None,*,pc_question=False):
    if features is None:
        return nas_answer('scope',0)
    state=features()
    # This flag comes from the authenticated requester and existing enabled
    # owner workflow at claim time. Text/history never supplies this permission.
    pc='업무툴이 실행 중인 PC의 고객사 평가기준·위험성평가·안전업무 문서와 양식 등 연결된 안전업무 폴더를 검색할 수 있습니다. PC 전체 드라이브를 검색하는 것은 아니며 사고자료·인증정보는 제외합니다.'
    if pc_question:
        return {'status':'COMPLETED','reply':pc} if state.get('owner_pc_lookup') is True else {'status':'NEEDS_INFO','reply':'현재 계정의 PC 자료 검색은 연결되어 있지 않습니다.'}
    value=nas_answer('scope',0)
    if state.get('owner_pc_lookup') is True:
        return {**value,'reply':value['reply']+'\n'+pc}
    return value


def answer(item, nas_answer, file_names=None, features=None, consent_context=None):
    if item.get('kind') != 'QUESTION' or item.get('source'):
        return None
    text = current_text(item['body'])
    if untargeted_consent(text):
        context = consent_context() if consent_context is not None else None
        if context is not None:
            state = context.get('status')
            if state == 'COMPLETED':
                reply = '앞선 파일 요청은 완료됐습니다. 아래 ‘준비된 파일 보기’에서 파일을 열어 주세요.' if context.get('files_available') else '앞선 요청은 이미 완료됐습니다. 추가로 필요한 작업을 적어 주세요.'
            elif state in {'AWAITING_REVIEW', 'AWAITING_RELEASE'}:
                reply = '앞선 자료는 확인 대기 중입니다. 아래 ‘요청 상태 보기’에서 확인해 주세요. 이 메시지로 승인이나 전달을 실행하지 않았습니다.'
            elif state in {'QUEUED', 'RUNNING'}:
                reply = '앞선 요청을 처리 중입니다. 아래 ‘요청 상태 보기’에서 진행 상황을 확인해 주세요.'
            elif state == 'NEEDS_INFO':
                reply = '앞선 요청에 자료 선택이나 추가 확인이 필요합니다. 아래 ‘요청 상태 보기’에서 확인해 주세요.'
            elif state in {'CANCELLED', 'INTERRUPTED', 'FAILED'}:
                reply = '앞선 요청은 중단된 상태입니다. 아래 ‘요청 상태 보기’에서 확인해 주세요. 다시 실행하지 않았습니다.'
            elif state == 'UNAVAILABLE':
                reply = '앞선 자료의 이용 권한이나 제공 상태를 확인해야 합니다. 승인이나 전달을 실행하지 않았습니다.'
            else:
                reply = None
            if reply:
                return {'status': 'COMPLETED', 'reply': reply}
        return {'status': 'NEEDS_INFO', 'reply': '승인할 요청을 특정하지 못했습니다. 대상 요청의 제목을 알려 주세요.'}
    if file_name_question(text) and file_names is not None:
        names = file_names()
        if not names:
            return {'status': 'NEEDS_INFO', 'reply': '이 대화에서 확인된 결과 파일이 없어 파일명을 특정할 수 없습니다.'}
        if len(names) == 1:
            return {'status': 'COMPLETED', 'reply': f'방금 제공한 파일은 ‘{names[0]}’입니다.'}
        return {'status': 'COMPLETED', 'reply': '직전에 제공한 파일입니다.\n' + '\n'.join(f'{i}. {name}' for i, name in enumerate(names, 1))}
    history = item['body'].rsplit('\n\n현재 요청:\n', 1)[0] if '\n\n현재 요청:\n' in item['body'] else ''
    provide_help = re.search(r'제공할?\s*방법|어떻게\s*제공', text) and re.search(r'모르|어떻|없', text)
    attachment_help = re.search(r'첨부\s*기능|사진.*첨부|첨부.*(?:아이콘|버튼)', text) and re.search(r'없|안\s*보|어디|못|방법|가능', text)
    if features is not None and len(text) <= 200 and (attachment_help or provide_help and re.search(r'NAS|나스|파일|자료|사진', history, re.I)):
        if provide_help:
            # Prior text selects only an already-authorized metadata operation;
            # it cannot supply a path, credentials, grant or executable action.
            prior_questions = re.findall(r'(?:^|\n)사용자: (.*?)\n답변:', history, re.S)
            for prior in reversed(prior_questions):
                recent = recent_request(prior)
                if recent is not None:
                    return nas_answer('recent', recent['limit'], recent['query']) if recent['query'] else nas_answer('recent', recent['limit'])
        if features().get('photos') is True:
            reply = '아래 ‘사진 첨부하기’를 눌러 주세요. ‘사진 연결 확인’이 보이면 먼저 눌러 주세요.'
            return {'status': 'COMPLETED', 'reply': reply}
        return {'status': 'NEEDS_INFO', 'reply': '이 답변 아래의 ‘사진 연결 확인’을 눌러 주세요. 작성한 질문은 그대로 유지됩니다.'}
    if re.search(r'질문|대화|채팅|히스토리|이력', text) and re.search(r'저장|쌓이|남아|남는|누적|기록|이어', text):
        return {'status': 'COMPLETED', 'reply': '질문과 답변은 본인 계정의 대화 이력에 저장됩니다. 같은 대화에서 이어서 질문할 수 있고, 아래 이력 버튼에서 이전 대화를 다시 열 수 있습니다.'}
    scope_question=source_scope_question(text)
    chat_question=(re.search(r'대화창|베스마채팅|BESMA',text,re.I) and re.search(r'뭘\s*할|무엇을|할\s*수',text))
    if (scope_question or chat_question) and not re.search(r'삭제|수정해|바꿔',text):
        value = source_scope_answer(nas_answer,features,pc_question=bool(re.search(r'PC|컴퓨터|드라이브',text,re.I))and not re.search(r'NAS|나스',text,re.I))
        if chat_question and value.get('status') == 'COMPLETED' and features is not None and features().get('photos') is True:
            value = {**value, 'reply': value['reply'] + '\n사진은 입력창 왼쪽 사진 아이콘으로 첨부할 수 있습니다.'}
        return value
    recent = recent_request(text)
    if recent is not None:
        return nas_answer('recent', recent['limit'], recent['query']) if recent['query'] else nas_answer('recent', recent['limit'])
    return None
