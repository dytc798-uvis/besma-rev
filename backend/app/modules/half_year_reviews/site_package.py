"""One site folder containing completed results and the original uploaded evidence."""
from io import BytesIO
from zipfile import ZipFile,ZIP_DEFLATED
from copy import deepcopy
import re
from .catalog import FORMS,Conflict
from . import exports
from .site_profile import enrich

def safe(value):
    value=re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',str(value)).strip(' .')[:100]
    return value if value and value not in {'.','..'}else'자료'

def build(store,key,site,period,profile):
    current=store.load(key);data=current['data'];members={};top=safe(site)+'_'+period
    def add(folder,name,raw):
        path=top+'/'+folder+'/'+safe(name)
        if path in members:
            if members[path]==raw:return
            stem,ext=path.rsplit('.',1)if'.'in path else(path,'')
            i=2
            while path in members:path=stem+'_'+str(i)+('.'+ext if ext else'');i+=1
        if sum(len(v)for v in members.values())+len(raw)>150*1024*1024:raise ValueError('PACKAGE_TOO_LARGE')
        members[path]=raw
    if not data.get('paper_completion'):
        for kind in FORMS:
            people=data['subjects'][kind]if FORMS[kind].get('needs_subject')else[{'id':'site','name':''}]
            if not people:raise ValueError('PACKAGE_INCOMPLETE')
            for who in people:
                assessment=data['assessments'].get(kind+':'+who['id'],{});done=assessment.get('completed')
                if not done or assessment.get('draft',{}).get('data')!=done['data']:raise ValueError('PACKAGE_INCOMPLETE')
                done=enrich(deepcopy(done),profile,assessment)
                raw=exports.pptx(done,site,done['inspector'],[],period)if kind=='report'else exports.hwpx(done,site,done['inspector'])if kind=='law'else exports.xlsx(kind,done,site,done['inspector'])
                name=FORMS[kind]['title']+('_'+who['name']if who['name']else'')+'.'+FORMS[kind]['format']
                add('결과표',name,raw)
    else:
        for meta in data['files']:
            if meta['evidence_id']in {'paper_assessment','paper_completion'}:add('결과표',meta['filename'],store.file(key,meta['id'])[0])
        if not any('/결과표/'in p for p in members):raise ValueError('PACKAGE_INCOMPLETE')
    for meta in data['files']:
        if meta['evidence_id']in {'paper_assessment','paper_completion'}:continue
        add('증빙자료',meta['filename'],store.file(key,meta['id'])[0])
    if current['revision']!=store.load(key)['revision']:raise Conflict('PACKAGE_CHANGED')
    out=BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED)as archive:
        archive.writestr(top+'/증빙자료/',b'')
        for path,raw in members.items():archive.writestr(path,raw)
    return out.getvalue(),top+'.zip'
