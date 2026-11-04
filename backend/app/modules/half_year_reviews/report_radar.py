"""Six existing report domains, normalized by their original point allocations."""
from collections import OrderedDict
from html import escape
import math
from .catalog import FORMS

LABELS=['위험성평가','안전조직','의견청취','비상대응','안전교육','건강검진']
def display_percent(value):return f'{value:.1f}'.rstrip('0').rstrip('.')+'%'
def values(snapshot):
    groups=OrderedDict();levels={'EXCELLENT':1,'NORMAL':.5,'POOR':0}
    for q in FORMS['report']['criteria']:
        answer=snapshot['data']['answers'].get(q['id'],{}).get('value')
        if answer not in levels:raise ValueError('COMPLETE_FIRST')
        group=groups.setdefault(q['group'],{'name':q['group'],'score':0,'max_score':0})
        group['score']+=q['max_score']*levels[answer];group['max_score']+=q['max_score']
    rows=list(groups.values())
    if len(rows)!=6:raise ValueError('RADAR_DOMAINS_CHANGED')
    for row,label in zip(rows,LABELS):row.update(label=label,percent=row['score']/row['max_score']*100)
    return rows

def page(snapshot,site):
    rows=values(snapshot);cx,cy,radius=380,255,174
    def point(index,ratio=1):
        angle=math.radians(-90+60*index);return cx+math.cos(angle)*radius*ratio,cy+math.sin(angle)*radius*ratio
    def points(ratios):return ' '.join(f'{x:.2f},{y:.2f}'for x,y in(point(i,v)for i,v in enumerate(ratios)))
    svg='<svg class="report-radar" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 510" role="img" aria-labelledby="radar-title radar-description"><title id="radar-title">분야별 안전보건평가 득점률</title><desc id="radar-description">'+escape(' · '.join(r['label']+' '+display_percent(r['percent'])for r in rows))+'</desc>'
    for percent in [25,50,75,100]:
        svg+='<polygon points="'+points([percent/100]*6)+'" fill="none" stroke="#cbd5e1" stroke-width="1.5"/>'
        svg+=f'<text x="388" y="{cy-radius*percent/100+5:.2f}" fill="#64748b" font-size="12">{percent}</text>'
    for i,row in enumerate(rows):
        x,y=point(i);lx,ly=point(i,1.32);anchor='middle'if i in [0,3]else'start'if i in [1,2]else'end'
        svg+=f'<line x1="{cx}" y1="{cy}" x2="{x:.2f}" y2="{y:.2f}" stroke="#cbd5e1" stroke-width="1.2"/>'
        svg+=f'<text x="{lx:.2f}" y="{ly-2:.2f}" text-anchor="{anchor}" font-size="18" font-weight="bold" fill="#172b4d">'+escape(row['label'])+f'<tspan x="{lx:.2f}" dy="23" font-size="17">'+display_percent(row['percent'])+'</tspan></text>'
    svg+='<polygon points="'+points([row['percent']/100 for row in rows])+'" fill="#186b88" fill-opacity=".22" stroke="#186b88" stroke-width="3"/>'
    for i,row in enumerate(rows):
        x,y=point(i,row['percent']/100);svg+=f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="#186b88"/>'
    svg+='</svg>'
    total=sum(r['score']for r in rows)
    body='<article class="radar-page"><header><p class="radar-kicker">반기 안전보건평가</p><h1>'+escape(site)+'</h1><p>'+escape(snapshot['data']['inspection_date'])+' · '+escape(snapshot.get('inspector',''))+'</p></header><section class="radar-total"><span>종합점수</span><strong>'+f'{total:g}'+'</strong><span>/ 100점</span></section><h2>분야별 평가</h2>'+svg
    body+='<table class="radar-table"><thead><tr><th>평가 분야</th><th>득점 / 배점</th><th>득점률</th></tr></thead><tbody>'
    for row in rows:body+='<tr><td>'+escape(row['label'])+'</td><td>'+f'{row["score"]:g} / {row["max_score"]:g}점</td><td>'+display_percent(row['percent'])+'</td></tr>'
    body+='</tbody></table><p class="radar-note">분야별 배점에 대한 득점률(%)입니다.</p>'
    body+='</article>'
    css='@page radar{size:A4 portrait;margin:14mm}.radar-page{page:radar;width:182mm;break-before:page;break-after:page;color:#172b4d}.radar-kicker{font-size:10pt;margin:0 0 3mm;color:#52657b}.radar-page h1{font-size:21pt;margin:0 0 3mm;line-height:1.25;overflow-wrap:anywhere}.radar-page header>p:last-child{font-size:10pt;margin:0}.radar-total{display:flex;align-items:baseline;gap:3mm;margin:5mm 0 2mm;padding:4mm 0;border-bottom:.4mm solid #cbd5e1}.radar-total strong{font-size:28pt}.radar-page h2{font-size:13pt;margin:4mm 0 0}.report-radar{display:block;width:100%;height:122mm}.radar-table th,.radar-table td{font-size:10pt;padding:2.5mm;border-color:#cbd5e1;text-align:center}.radar-table th{background:#edf3f7}.radar-table td:first-child{text-align:left}.radar-low{background:#fff0d9}.radar-note{font-size:9pt;color:#52657b;margin:2mm 0}.radar-focus{font-size:10pt;line-height:1.5;margin:4mm 0 0}'
    return body,css+' .report-radar{margin-bottom:4mm}'
