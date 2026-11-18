import re

# This only decides whether to offer already authorized original bytes. It does
# not resolve a path, authorize a source, or change the model's factual answer.
_REQUEST=re.compile(r'(?:원본|파일|첨부)도|(?:원본|파일)\s*(?:다운로드|받기)|(?:원본|파일)(?:을|를)?\s*(?:첨부|보내|전달)|함께\s*(?:보내|첨부)|(?:다운로드|내려받|다운받)|(?:원본|원문|파일)(?:을|를)?\s*(?:받게|열어|찾아)|(?:자료|양식|계획서|절차서|평가표|보고서)(?:를|을)?\s*(?:찾아|보내|열어)|^\s*(?:원본|원문|파일)\s*[.!?]?\s*$')
_NEGATED=re.compile(r'^(?:는|은|을|를|도|가|이)?\s*(?:(?:주|줘|주시|주지|보내|전달|첨부|받|하|해|하지|보내지|전달하지|첨부하지|받지)(?:[가-힣]{0,5})?\s*)?(?:말|마(?:\s|$|[.!?])|않|안\s*해|필요\s*(?:없|하지\s*않)|불필요|제외|빼|안\s*(?:해|하|보내|전달|첨부|받)|나중(?:에)?\s*(?:할|받|보내|다운로드))')

_CANCEL=re.compile(r'(?:(?:첨부|파일|원본|다운로드|전송)(?:은|는|을|를)?\s*(?:요청\s*)?취소|(?:원본|원문|파일|첨부|다운로드|내려받(?:기|지)?)(?:은|는|을|를|도|가|이)?\s*(?:(?:보내|전달|첨부|다운로드|받|하|해|주)(?:[가-힣]{0,5})?\s*)?(?:말|마(?:\s|$|[.!?])|않|안\s*(?:보내|받|하)|필요\s*(?:없|하지\s*않)|불필요|제외|빼|안\s*(?:해|하|보내|전달|첨부|받)|나중(?:에)?\s*(?:할|받|보내|다운로드)))')

_INQUIRY=re.compile(r'^(?:(?:하|받|보내|열)?(?:으?려면|으?려는)|는\s*(?:방법|절차|이유)|(?:가|이)\s*(?:안\s*(?:되|돼|되는|열|받)|실패|불가|오류)|(?:달라는|주라는|줘라는)\s*(?:게|건|것이|뜻이)?\s*아니(?:라|고|에요|야|다|라고))')

def answer_only_requested(body):
    current=re.split(r'현재\s*요청\s*[:：]',body)[-1]
    events=[(m.end(),False) for m in _CANCEL.finditer(current)]
    for match in _REQUEST.finditer(current):
        # Check the action and its polarity together: '보내지 말고' and
        # '다운로드는 필요 없고' are not requests for attachment. A later
        # affirmative request still wins ('설명만 말고 원본도 보내').
        tail=current[match.end():].lstrip()
        action=match.group()
        if re.search(r'보내|전달|첨부|찾아|열어|받게',action):
            tail=re.sub(r'^지\s*', '', tail)
        if not _NEGATED.match(tail) and not _INQUIRY.match(tail):events.append((match.end(),True))
    return not (sorted(events)[-1][1] if events else False)
