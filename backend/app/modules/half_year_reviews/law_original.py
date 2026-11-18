"""Fill the registered native form without rebuilding its table or approval block."""
from pathlib import Path
from html import escape
import base64,hashlib,json,unicodedata
from .catalog import FORMS

ROOT=Path(__file__).with_name('assets')/'law-original'

def fit_size(value,width,height):
    for size in [8,7.75,7.5,7.25,7,6.75,6.5,6.25,6]:
        capacity=(width-6)/size;lines=1;used=0
        for ch in value:
            unit=1 if unicodedata.east_asian_width(ch)in {'W','F'}else .55
            if ch=='\n':lines+=1;used=0;continue
            if used+unit>capacity:lines+=1;used=0
            used+=unit
        if lines*size*1.25<=height-4:return size
    raise ValueError('LAW_PRINT_NOTE_TOO_LONG')

def document(snapshot,site,summary=''):
    layout=json.loads((ROOT/'layout.json').read_text('utf8'));pages=[];answers=snapshot['data']['answers']
    def field(value,left,top,width,height,size=9,center=False):
        return '<div class="law-input" style="left:%gpt;top:%gpt;width:%gpt;height:%gpt;font-size:%gpt;%s">%s</div>'%(left,top,width,height,size,'justify-content:center;text-align:center;'if center else'',escape(str(value)))
    for index,page in enumerate(layout['pages']):
        raw=(ROOT/page['filename']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=page['sha256']:raise ValueError('TEMPLATE_CHANGED')
        body='<img class="law-form" alt="" src="data:image/svg+xml;base64,'+base64.b64encode(raw).decode()+'">'
        if index==0:
            label=layout['site_label'];body+=field(site,label[2]+4,label[1]-1,310,17,10)
            label=layout['manager_label'];body+=field(snapshot.get('site_manager',''),label[2]+4,label[1]-1,73,16,10)
            body+=field(snapshot['data']['inspection_date'],94,74,92,27,9,True)
            body+=field(snapshot.get('inspector',''),94,103,92,26,10,True)
        criteria=[q for q in FORMS['law']['criteria']if q['table']==index+1]
        if len(criteria)!=len(page['ys'])-1:raise ValueError('TEMPLATE_CHANGED')
        xs=page['xs']
        for r,q in enumerate(criteria):
            a=answers[q['id']];top=page['ys'][r];height=page['ys'][r+1]-top;note=('해당없음: 'if a['value']=='NA'else'')+a.get('note','');width=xs[5]-xs[4]
            body+=field(note,xs[4]+1,top+1,width-2,height-2,fit_size(note,width-2,height-2))
            if a['value']in {'PASS','FAIL'}:
                col=5 if a['value']=='PASS'else 6;body+=field('✓',xs[col]+1,top+1,xs[col+1]-xs[col]-2,height-2,11,True)
        if index==3 and summary:
            y=page['ys'][-1]+10;body+='<section class="law-total" style="top:%gpt"><b>총평</b><div>%s</div></section>'%(y,escape(summary))
        pages.append('<article class="law-original">'+body+'</article>')
    css='@page{size:841pt 595pt;margin:0}.law-original{position:relative;width:841pt;height:595pt;break-after:page}.law-form{position:absolute;inset:0;width:841pt;height:595pt}.law-input{position:absolute;display:flex;align-items:center;padding:1pt 2pt;line-height:1.25;white-space:pre-wrap;overflow-wrap:anywhere;font-family:"Malgun Gothic","Noto Sans CJK KR",sans-serif}.law-total{position:absolute;left:29.73pt;width:784.18pt;border:.6pt solid #333;padding:7pt;font-size:9pt;line-height:1.4}.law-total>div{margin-top:4pt;white-space:pre-wrap}@media screen{.law-original{margin:12px auto}}'
    return ''.join(pages),css
