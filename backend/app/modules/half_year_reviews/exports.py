from pathlib import Path
from xml.etree import ElementTree as E
from copy import deepcopy
import zipfile,io,hashlib,re,posixpath
from xml.sax.saxutils import escape
from .catalog import ASSETS,CATALOG,FORMS,report_schema
from app.modules.inspection_reports.pptx_report import make_report,NS,text,cell,shape,xml
def template(name):
    data=(ASSETS/name).read_bytes()
    if hashlib.sha256(data).hexdigest()!=CATALOG['template_hashes'][name]:raise ValueError('TEMPLATE_CHANGED')
    return data
def parts(data):
    with zipfile.ZipFile(io.BytesIO(data))as z:return {name:z.read(name)for name in z.namelist()}
def pack(items,hwpx=False):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED)as z:
        for name,data in items.items():z.writestr(name,data,compress_type=zipfile.ZIP_STORED if hwpx and name=='mimetype'else zipfile.ZIP_DEFLATED)
    return output.getvalue()

def template_bundle():
    # Reuse exactly the four individually available output templates.
    order=CATALOG['order']
    if len(order)!=4 or set(order)!={'report','law','manager','supervisor'}:raise ValueError('TEMPLATE_CHANGED')
    files={}
    for form in order:
        schema=FORMS[form];name=schema['title']+'_출력용.'+schema['format']
        if name in files or '/'in name or '\\'in name:raise ValueError('TEMPLATE_CHANGED')
        files[name]=template(schema.get('template','반기평가표.pptx'))
    return pack(files)
def xlsx(form,snapshot,site,inspector):
    schema=FORMS[form];items=parts(template(schema['template']));uri='http://schemas.openxmlformats.org/spreadsheetml/2006/main';ns={'s':uri};q=lambda tag:'{'+uri+'}'+tag
    workbook=E.fromstring(items['xl/workbook.xml']);sheet_ref=next(s for s in workbook.find('s:sheets',ns)if s.get('name')=='평가표');rid=sheet_ref.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
    relationships=E.fromstring(items['xl/_rels/workbook.xml.rels']);target=next(r.get('Target')for r in relationships if r.get('Id')==rid);part=posixpath.normpath('xl/'+target)if not target.startswith('/')else target.lstrip('/')
    if not part.startswith('xl/worksheets/'):raise ValueError('TEMPLATE_SHEET_INVALID')
    root=E.fromstring(items[part]);changes={}
    def setcell(address,value,formula=None,cache=None):
        if formula:changes[address]=('', '<f>'+escape(formula)+'</f><v>'+str(cache)+'</v>')
        elif isinstance(value,(int,float)):changes[address]=('', '<v>'+str(value)+'</v>')
        else:changes[address]=(' t="inlineStr"','<is><t xml:space="preserve">'+escape(str(value))+'</t></is>')
    data=snapshot['data'];day=data['inspection_date'];subject=snapshot.get('subject_name')or(snapshot.get('site_manager','')if form=='manager'else'')
    for address,value in ({'B2':site,'P2':day,'U2':subject,'Y2':inspector}if form=='manager'else{'C2':site,'M2':day,'S2':subject,'Y2':inspector}).items():setcell(address,value)
    for criterion in schema['criteria']:
        answer=data['answers'][criterion['id']];setcell('X'+str(criterion['row']),answer['value']);setcell('Y'+str(criterion['row']),answer['note'])
    score=snapshot['result']['score'];total=schema['total_cell']
    existing=root.find(".//s:c[@r='"+total+"']/s:f",ns)
    if existing is not None:setcell(total,None,formula=existing.text,cache=score)
    else:setcell(total,score)
    setcell(schema['summary_cell'],data['summary'])
    seen=set()
    def patch(match):
        raw=match.group(0);opening=raw.split('>',1)[0];address=re.search(r'\br="([A-Z]+\d+)"',opening).group(1)
        if address not in changes:return raw
        seen.add(address);attributes=opening[2:].rstrip('/');attributes=re.sub(r'\s+t="[^"]*"','',attributes);kind,content=changes[address]
        return '<c'+attributes+kind+'>'+content+'</c>'
    # Patch only known input cells. Retain every original namespace binding,
    # including prefixes referenced by mc:Ignorable and extension metadata.
    source=items[part].decode('utf-8');source=re.sub(r'<c\b[^>]*?/\s*>|<c\b[^>]*?>.*?</c>',patch,source,flags=re.S)
    if seen!=set(changes):raise ValueError('TEMPLATE_INPUT_CELL_MISSING')
    items[part]=source.encode('utf-8')
    return pack(items)
def hwpx(snapshot,site,inspector):
    items=parts(template('law.hwpx'));uri='http://www.hancom.co.kr/hwpml/2011/paragraph';ns={'hp':uri};root=E.fromstring(items['Contents/section0.xml']);tables=root.findall('.//hp:tbl',ns)
    def tc(table,row,col):
        for c in tables[table].findall('.//hp:tc',ns):
            a=c.find('hp:cellAddr',ns)
            if a is not None and a.get('rowAddr')==str(row)and a.get('colAddr')==str(col):return c
        raise ValueError('LAW_CELL_MISSING')
    def fill(target,value):
        paragraphs=target.findall('hp:subList/hp:p',ns)
        for i,p in enumerate(paragraphs):
            runs=p.findall('hp:run',ns)
            if not runs:runs=[E.SubElement(p,'{'+uri+'}run',{'charPrIDRef':'0'})]
            for run in runs:
                for n in list(run):run.remove(n)
            E.SubElement(runs[0],'{'+uri+'}t').text=str(value)if i==0 else''
            # Native layout must recalculate the inserted characters.
            segment=p.find('hp:linesegarray',ns)
            if segment is not None:p.remove(segment)
    data=snapshot['data'];fill(tc(0,0,2),'안전법규준수 점검표\n현장명: '+site+'    현장소장: '+snapshot.get('site_manager','')+'  (인)');fill(tc(0,1,1),data['inspection_date']);fill(tc(0,2,1),inspector)
    for criterion in FORMS['law']['criteria']:
        answer=data['answers'][criterion['id']];row=criterion['row'];table=criterion['table'];value=answer['value'];note=answer['note']
        fill(tc(table,row,4),('해당없음: 'if value=='NA'else'')+note);fill(tc(table,row,5),'✓'if value=='PASS'else'');fill(tc(table,row,6),'✓'if value=='FAIL'else'')
    if data.get('summary'):
        seed=root.findall('hp:p',ns)[-1];next_id=max([int(p.get('id','0'))for p in root.iter('{'+uri+'}p')if p.get('id','0').isdigit()]+[0])+1
        for content in ['총평',*data['summary'].splitlines()]:
            paragraph=deepcopy(seed);paragraph.set('id',str(next_id));paragraph.set('paraPrIDRef','0');paragraph.set('pageBreak','0');next_id+=1
            for child in list(paragraph):paragraph.remove(child)
            run=E.SubElement(paragraph,'{'+uri+'}run',{'charPrIDRef':'0'});E.SubElement(run,'{'+uri+'}t').text=content;root.append(paragraph)
    items['Contents/section0.xml']=E.tostring(root,encoding='utf-8',xml_declaration=True);items['Preview/PrvText.txt']='\n'.join(root.itertext()).encode('utf-8')
    return pack(items,True)
def pptx(snapshot,site,inspector,photos,period,blind=False):
    template_path=Path(__file__).parents[1]/'inspection_reports/assets/반기평가표.pptx';data=snapshot['data'];fields={'site_name':site,'inspection_date':data['inspection_date'],'inspector':inspector,'summary':data['summary'],'evaluation_period':period.replace('-H1','년 상반기').replace('-H2','년 하반기')}
    if photos:items=parts(make_report(template_path.read_bytes(),fields,photos))
    else:
        from datetime import date
        day=date.fromisoformat(data['inspection_date']);items=parts(template_path.read_bytes());cover=E.fromstring(items['ppt/slides/slide1.xml']);text(cell(cover,6,0,1),site);text(cell(cover,6,1,1),day.strftime('%Y.%m.%d'));text(shape(cover,5),f'{day.year}년 '+('상'if day.month<=6 else'하')+'반기');items['ppt/slides/slide1.xml']=xml(cover)
        overview=E.fromstring(items['ppt/slides/slide2.xml']);text(cell(overview,7,1,1),site);text(cell(overview,7,3,1),day.strftime('%Y.%m.%d'));text(cell(overview,7,5,1),inspector);items['ppt/slides/slide2.xml']=xml(overview)
        confirm=E.fromstring(items['ppt/slides/slide6.xml']);text(cell(confirm,7,0,1),site);text(cell(confirm,7,0,3),day.strftime('%Y.%m.%d'));text(cell(confirm,7,1,1),fields['evaluation_period']);text(cell(confirm,9,0,0),data['summary']);text(cell(confirm,11,0,1),inspector+'  (서명)');items['ppt/slides/slide6.xml']=xml(confirm)
    overview=E.fromstring(items['ppt/slides/slide2.xml'])
    progress=snapshot.get('progress','')+(' ('+snapshot['progress_date']+' 기준)'if snapshot.get('progress')and snapshot.get('progress_date')else'')
    for row,value in [(2,' / '.join(filter(None,[snapshot.get('contractor',''),snapshot.get('trade','')]))),(4,' / '.join(filter(None,[snapshot.get('site_manager',''),snapshot.get('safety_staff','')]))),(6,' / '.join(filter(None,[snapshot.get('construction_amount',''),progress])))]:text(cell(overview,7,row,1),value)
    items['ppt/slides/slide2.xml']=xml(overview)
    summary=E.fromstring(items['ppt/slides/slide3.xml']);score=snapshot['result']['score']
    text(shape(summary,8),''if blind else f'{score:g}');text(cell(summary,12,19,5),''if blind else f'{score:g}')
    for criterion in report_schema(snapshot)['criteria']:
        if snapshot.get('criteria_version',1)>=2:
            text(cell(summary,12,criterion['row'],2),criterion['title']);text(cell(summary,12,criterion['row'],3),criterion['description']);text(cell(summary,12,criterion['row'],4),str(criterion['max_score']))
        level=data['answers'][criterion['id']]['value'];points=criterion['max_score']*{'EXCELLENT':1,'NORMAL':.5,'POOR':0}[level];text(cell(summary,12,criterion['row'],5),('미흡'if points<=1 else'')if blind else f'{points:g}')
        if blind and points<=1:
            for target in shape(summary,12).findall('.//a:tr',NS)[criterion['row']].findall('a:tc',NS):
                prop=target.find('a:tcPr',NS)
                if prop is None:prop=E.SubElement(target,'{'+NS['a']+'}tcPr')
                for prior in list(prop):
                    if prior.tag in {'{'+NS['a']+'}solidFill','{'+NS['a']+'}noFill'}:prop.remove(prior)
                fill=E.SubElement(prop,'{'+NS['a']+'}solidFill');E.SubElement(fill,'{'+NS['a']+'}srgbClr',{'val':'FFF0D9'})
                for run in target.findall('.//a:rPr',NS):run.set('b','1')
        note=data['answers'][criterion['id']]['note']
        if note:
            target=cell(summary,12,criterion['row'],3);prior=''.join(target.itertext());text(target,prior+'  '+note)
    items['ppt/slides/slide3.xml']=xml(summary)
    improvement=E.fromstring(items['ppt/slides/slide4.xml']);rows=data['improvements'];text(shape(improvement,7),'개선요구'+(' '+str(len(rows))+'건'if rows else''))
    for target in shape(improvement,8).findall('.//a:tr',NS)[1:]:
        for slot in target.findall('a:tc',NS):text(slot,'')
    for i,row in enumerate(rows,1):
        text(cell(improvement,8,i,0),str(i))
        for col,key in enumerate(['finding','action','owner','due'],1):text(cell(improvement,8,i,col),row[key])
    items['ppt/slides/slide4.xml']=xml(improvement);confirm=E.fromstring(items['ppt/slides/slide6.xml']);text(cell(confirm,7,1,3),''if blind else f'{score:g} / 100점');text(cell(confirm,7,2,1),rows[0]['finding']if len(rows)==1 else(str(len(rows))+'건 (개선요구사항 참조)'if rows else''));text(cell(confirm,7,2,3),'');text(cell(confirm,9,0,0),data.get('summary',''));text(cell(confirm,11,0,1),inspector+'    (서명)');text(cell(confirm,11,0,3),snapshot.get('site_manager','')+'    (서명)')
    for col in [1,3]:
        target=cell(confirm,11,0,col)
        for paragraph in target.findall('.//a:p',NS):
            prop=paragraph.find('a:pPr',NS)
            if prop is None:prop=E.Element('{'+NS['a']+'}pPr');paragraph.insert(0,prop)
            prop.set('algn','l');prop.set('marL','90000')
    items['ppt/slides/slide6.xml']=xml(confirm)
    return pack(items)
