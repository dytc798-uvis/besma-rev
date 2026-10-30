"""Site workspace identity and customer boundaries. No role or data mutation."""
import re,unicodedata
from fastapi import HTTPException


def require_site_identity(user):
    role=getattr(getattr(user,'role',None),'value',getattr(user,'role',None))
    ui=getattr(getattr(user,'ui_type',None),'value',getattr(user,'ui_type',None))
    ident=getattr(user,'site_id',None)
    if (not getattr(user,'is_active',False) or getattr(user,'must_change_password',False)
        or getattr(user,'government_preview',False)or role!='SITE'or ui!='SITE'
        or type(ident)is not int or ident<1):raise HTTPException(403,'현장 계정의 소속을 확인해 주세요.')
    return ident


def require_own_site(user,site):
    ident=require_site_identity(user)
    if site is None or site.id!=ident:raise HTTPException(403,'로그인한 현장의 자료만 확인할 수 있습니다.')
    return site


def site_menus(user,site,government):
    require_own_site(user,site)
    if type(government)is not bool:raise ValueError('VERIFIED_GOVERNMENT_SCOPE_REQUIRED')
    entries=[(1,'기능인인정제','functional','/site/functional-eval/roster'),
        (2,'업무분장','duties','/workspace.html#duties'),
        (3,'위험성평가 DB','risks','/site/risk-library'),
        (4,'양식·법령 탐색','forms','/workspace.html#forms'),
        (5,'현장 정보 검색','sites','/site/mobile/site-search'),
        (6,'고객사 안전기준','contractors','/workspace.html#contractors'),
        (7,'관급공사 현장 소통'if government else'의견·홈페이지 개선','government','/workspace.html#government'if government else'/site/opinions'),
        (8,'사용설명서','guide','/site/user-guide'),
        (9,'근로자의견청취','voice','/site/google-feedback'),
        (14,'설정','settings','/workspace.html#settings')]
    return [{'id':n,'title':title,'key':key,'href':href}for n,title,key,href in entries]


def customer_key(value):
    return re.sub(r'주식회사|\(주\)|\s','',unicodedata.normalize('NFKC',str(value or ''))).casefold()


_ALIASES={
    '대우건설':'대우','롯데건설':'롯데','두산건설':'두산','쌍용건설':'쌍용','한화건설':'한화',
    '금호건설':'금호','신세계건설':'신세계','진흥기업':'진흥','대보건설':'대보','한양건설':'한양',
    '한라건설':'한라','부영주택':'부영','부영건설':'부영','대광건영':'대광','대광로제비앙':'대광',
    '포스코건설':'포스코','포스코이앤씨':'포스코','gs건설':'gs','지에스건설':'gs',
    'hdc현대산업개발':'현대산업개발','에이치디씨현대산업개발':'현대산업개발'}
_SCOPES={
    '삼성물산':('삼성',('삼성물산',)),
    '삼성이앤에이':('삼성',('삼성이앤에이','삼성e&a')),
    '삼성e&a':('삼성',('삼성이앤에이','삼성e&a')),
    'dl건설':('dl',('dl건설','디엘건설')),'디엘건설':('dl',('dl건설','디엘건설')),
    'dl이앤씨':('dl',('dl이앤씨','디엘이앤씨','dle&c')),
    '디엘이앤씨':('dl',('dl이앤씨','디엘이앤씨','dle&c')),
    'dle&c':('dl',('dl이앤씨','디엘이앤씨','dle&c'))}


def policy_belongs_to_site(item,site):
    """Use server site columns; URL/customer query strings cannot broaden a grant."""
    group=customer_key(item.get('contractor'));title=customer_key(item.get('title'))
    for raw in [getattr(site,'client_name',None),getattr(site,'contractor_name',None)]:
        key=customer_key(raw)
        if not key:continue
        if key in _SCOPES:
            family,words=_SCOPES[key]
            if group==family and any(word in title for word in words):return True
        elif key not in {'삼성','dl'} and group==_ALIASES.get(key,key):return True
    return False
