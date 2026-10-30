"""Use existing account and index facts before a text-only model is consulted."""
import re


def current_text(body):
    return body.rsplit('\n\n현재 요청:\n', 1)[-1]


def file_name_question(text):
    return bool(len(text) <= 160 and re.search(r'방금|직전|앞서|아까|그\s*(?:파일|자료|문서)|이\s*(?:파일|자료|문서)', text)
                and re.search(r'파일명|(?:파일|자료|문서).*이름', text)
                and not re.search(r'내용|요약|분석|수정|바꿔|변경|삭제|만들|생성|작성|보내\s*(?:줘|주세요|라)|첨부\s*해|다운로드\s*해|열어', text))


def recent_limit(text):
    if (re.search(r'최근|마지막|수정일', text) and re.search(r'파일|자료|문서', text)
            and not re.search(r'내용|조항|적용|출역|인원|공수|수치', text)
            and not re.search(r'수정해|바꿔|삭제|만들|생성', text)):
        match = re.search(r'(\d{1,2})\s*개', text)
        return min(10, max(1, int(match.group(1)))) if match else 3
    return None


def answer(item, nas_answer, file_names=None, features=None):
    if item.get('kind') != 'QUESTION' or item.get('source'):
        return None
    text = current_text(item['body'])
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
                limit = recent_limit(prior)
                if limit is not None:
                    return nas_answer('recent', limit)
        if features().get('photos') is True:
            reply = '사진은 입력창 왼쪽 사진 아이콘으로 첨부할 수 있습니다.'
            if nas_answer('scope', 0).get('status') == 'COMPLETED':
                reply += ' NAS 자료는 파일 목록을 옮기지 않고 이 대화에서 검색을 요청하시면 됩니다.'
            return {'status': 'COMPLETED', 'reply': reply}
        return {'status': 'NEEDS_INFO', 'reply': '현재 사진 첨부 연결을 확인하지 못했습니다. NAS 파일 목록을 복사해 보내실 필요는 없습니다.'}
    if re.search(r'질문|대화|채팅|히스토리|이력', text) and re.search(r'저장|쌓이|남아|남는|누적|기록|이어', text):
        return {'status': 'COMPLETED', 'reply': '질문과 답변은 본인 계정의 대화 이력에 저장됩니다. 같은 대화에서 이어서 질문할 수 있고, 아래 이력 버튼에서 이전 대화를 다시 열 수 있습니다.'}
    scope_question=(re.search(r'나스|NAS|파일|자료',text,re.I) and re.search(r'범위|어디까지|탐색할|탐색이',text))
    chat_question=(re.search(r'대화창|베스마채팅|BESMA',text,re.I) and re.search(r'뭘\s*할|무엇을|할\s*수',text))
    if (scope_question or chat_question) and not re.search(r'삭제|수정해|바꿔',text):
        value = nas_answer('scope', 0)
        if chat_question and value.get('status') == 'COMPLETED' and features is not None and features().get('photos') is True:
            value = {**value, 'reply': value['reply'] + '\n사진은 입력창 왼쪽 사진 아이콘으로 첨부할 수 있습니다.'}
        return value
    limit = recent_limit(text)
    if limit is not None:
        return nas_answer('recent', limit)
    return None
