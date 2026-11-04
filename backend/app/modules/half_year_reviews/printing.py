"""Printable views derived from the existing four filled document templates."""
from html import escape
from xml.etree import ElementTree as E
from io import BytesIO
import base64,posixpath
from . import exports
from .catalog import FORMS

A='http://schemas.openxmlformats.org/drawingml/2006/main'
P='http://schemas.openxmlformats.org/presentationml/2006/main'
NS={'a':A,'p':P}
def text(node,tag='{'+A+'}p',leaf='{'+A+'}t'):
    return '\n'.join(''.join(t.text or''for t in p.iter(leaf))for p in node.iter(tag))
def safe(value):return escape(str(value if value is not None else'')).replace('\n','<br>')
def number(node,key,default=0):return float(node.get(key,default))if node is not None else default

def pptx(raw):
    items=exports.parts(raw);presentation=E.fromstring(items['ppt/presentation.xml']);size=presentation.find('p:sldSz',NS)
    width=number(size,'cx')/36000;height=number(size,'cy')/36000;pages=[]
    for index in [1,2,3,4,6]:
        root=E.fromstring(items[f'ppt/slides/slide{index}.xml']);shapes=[]
        for node in root.findall('p:cSld/p:spTree/*',NS):
            xfrm=node.find('p:xfrm',NS)if node.tag=='{'+P+'}graphicFrame'else node.find('p:spPr/a:xfrm',NS)
            if xfrm is None:continue
            off=xfrm.find('a:off',NS);ext=xfrm.find('a:ext',NS)
            if off is None or ext is None:continue
            style=f'left:{number(off,"x")/36000}mm;top:{number(off,"y")/36000}mm;width:{number(ext,"cx")/36000}mm;height:{number(ext,"cy")/36000}mm;'
            table=node.find('.//a:tbl',NS)
            if table is not None:
                cols=table.findall('a:tblGrid/a:gridCol',NS);total=sum(number(c,'w')for c in cols)or 1
                html='<table><colgroup>'+''.join(f'<col style="width:{100*number(c,"w")/total}%">'for c in cols)+'</colgroup>'
                for row in table.findall('a:tr',NS):
                    html+=f'<tr style="height:{number(row,"h")/36000}mm">'
                    for cell in row.findall('a:tc',NS):
                        if cell.get('hMerge')=='1'or cell.get('vMerge')=='1':continue
                        sizes=[number(r,'sz')/100 for r in cell.findall('.//a:rPr',NS)if r.get('sz')]
                        font=min(sizes)if sizes else 9
                        emphasis=cell.find('a:tcPr/a:solidFill/a:srgbClr',NS);extra='background:#fff0d9;font-weight:bold;'if emphasis is not None and emphasis.get('val')=='FFF0D9'else''
                        paragraph=cell.find('.//a:pPr',NS)
                        if paragraph is not None and paragraph.get('algn')=='l':extra+='text-align:left;padding-left:2.5mm;'
                        if '(서명)'in text(cell):extra+='white-space:pre-wrap;'
                        html+=f'<td colspan="{cell.get("gridSpan","1")}" rowspan="{cell.get("rowSpan","1")}" style="font-size:{font}pt;{extra}">'+safe(text(cell))+'</td>'
                    html+='</tr>'
                html+='</table>'
            else:
                value=text(node)
                if not value.strip():continue
                sizes=[number(r,'sz')/100 for r in node.findall('.//a:rPr',NS)if r.get('sz')]
                font=min(sizes)if sizes else 12
                html=f'<div style="font-size:{font}pt;white-space:pre-wrap">'+escape(value)+'</div>'
            shapes.append('<div class="shape" style="'+style+'">'+html+'</div>')
        pages.append('<article class="slide">'+''.join(shapes)+'</article>')
    return ''.join(pages),f'@page{{size:{width}mm {height}mm;margin:0}}.slide{{width:{width}mm;height:{height}mm;position:relative;break-after:page;overflow:hidden}}.shape{{position:absolute}}.shape table{{height:100%}}.shape td{{padding:.5mm;line-height:1.12;text-align:center}}'

def xlsx(raw,site_manager=""):
    import openpyxl
    book=openpyxl.load_workbook(BytesIO(raw),data_only=True);sheet=book['평가표'];merged={};covered=set()
    for rect in sheet.merged_cells.ranges:
        merged[(rect.min_row,rect.min_col)]=(rect.max_row-rect.min_row+1,rect.max_col-rect.min_col+1)
        covered.update((r,c)for r in range(rect.min_row,rect.max_row+1)for c in range(rect.min_col,rect.max_col+1)if(r,c)!=(rect.min_row,rect.min_col))
    from openpyxl.utils.cell import range_boundaries,get_column_letter
    areas=list(sheet.print_area.ranges)if hasattr(sheet.print_area,'ranges')else[]
    area=str(areas[0]).split('!')[-1]if areas else str(sheet.print_area).split('!')[-1].replace("'",'')
    try:left,top,right,bottom=range_boundaries(area)
    except ValueError:left,top,right,bottom=1,1,min(sheet.max_column,30),min(sheet.max_row,50)
    # Excel column dimensions may cover ranges (K:V); absent keys are not width 13.
    def column_width(c):
        for dim in sheet.column_dimensions.values():
            if dim.min<=c<=dim.max:return dim.width
        return sheet.sheet_format.defaultColWidth or 8.43
    widths=[int(column_width(c)*7+5)for c in range(left,right+1)];total=sum(widths)
    scale=(sheet.page_setup.scale or 100)/100
    width=total*25.4/96*scale
    html=f'<article class="sheet" style="width:{width}mm"><table><colgroup>'+''.join(f'<col style="width:{100*w/total}%">'for w in widths)+'</colgroup>'
    for r in range(top,bottom+1):
        html+='<tr style="height:'+str((sheet.row_dimensions[r].height or sheet.sheet_format.defaultRowHeight)*scale)+'pt">'
        for c in range(left,right+1):
            if(r,c)in covered:continue
            cell=sheet.cell(r,c);rows,cols=merged.get((r,c),(1,1));border=cell.border
            style='font-size:'+str((cell.font.sz or 10)*scale)+'pt;font-weight:'+('bold'if cell.font.b else'normal')+';text-align:'+(cell.alignment.horizontal if cell.alignment.horizontal in {'left','right','center'}else'left')+';'
            for edge in ['top','bottom','left','right']:
                side=getattr(border,edge)
                style+='border-'+edge+(':.3mm solid #222;'if side and side.style else':0;')
            html+=f'<td rowspan="{rows}" colspan="{cols}" style="{style}">'+safe(cell.value if cell.value is not None else'')+'</td>'
        html+='</tr>'
    margins=sheet.page_margins;css=f'@page{{size:A4 portrait;margin:{margins.top*25.4}mm {margins.right*25.4}mm {margins.bottom*25.4}mm {margins.left*25.4}mm}}.sheet td{{padding:{.4*scale}mm;line-height:1.1}}.sheet table{{table-layout:fixed}}'
    book.close();return html+'</table><p class="signature-line">현장소장: '+safe(site_manager)+'    (서명)</p></article>',css+' .sheet tr{break-inside:avoid}.signature-line{font-size:11pt;text-align:right;margin:8mm 0 0;break-inside:avoid}'

def hwpx(raw):
    items=exports.parts(raw);root=E.fromstring(items['Contents/section0.xml']);hp='http://www.hancom.co.kr/hwpml/2011/paragraph';ns={'hp':hp};tables=[]
    for table_index,table in enumerate(root.findall('.//hp:tbl',ns)):
        rows={};columns={}
        for cell in table.findall('hp:tr/hp:tc',ns):
            addr=cell.find('hp:cellAddr',ns);span=cell.find('hp:cellSpan',ns);size=cell.find('hp:cellSz',ns)
            r=int(addr.get('rowAddr'));c=int(addr.get('colAddr'));cs=int(span.get('colSpan','1'));rs=int(span.get('rowSpan','1'))
            rows.setdefault(r,[]).append((c,cs,rs,cell))
            if cs==1:columns[c]=number(size,'width')
        total=sum(columns.values())or 1
        html='<table class="law-table">'
        if columns and set(columns)==set(range(max(columns)+1)):html+='<colgroup>'+''.join(f'<col style="width:{100*columns[c]/total}%">'for c in sorted(columns))+'</colgroup>'
        for row_index,(r,cells)in enumerate(sorted(rows.items())):
            if table_index>0 and row_index==0:html+='<thead>'
            elif table_index>0 and row_index==2:html+='<tbody>'
            html+='<tr>'
            for c,cs,rs,cell in sorted(cells,key=lambda x:x[0]):
                value=text(cell,'{'+hp+'}p','{'+hp+'}t')
                html+=f'<td colspan="{cs}" rowspan="{rs}">'+safe(value)+'</td>'
            html+='</tr>'
            if table_index>0 and row_index==1:html+='</thead>'
        if table_index>0 and len(rows)>2:html+='</tbody>'
        tables.append(html+'</table>')
    return '<article class="law">'+''.join(tables)+'</article>','@page{size:A4 portrait;margin:12mm}.law{width:186mm}.law td{font-size:9pt;padding:1mm;line-height:1.2}.law-table{margin-bottom:3mm}.law-table tr{break-inside:avoid}'

def document(form,snapshot,site,period,blind=True):
    from copy import deepcopy
    snapshot=deepcopy(snapshot);comments=[]
    for index,criterion in enumerate(FORMS[form]['criteria'],1):
        answer=snapshot['data']['answers'][criterion['id']];note=answer.get('note','')
        if len(note)>(30 if form=='law'else 20)or '\n'in note:
            comments.append((str(index)+'. '+criterion['title'],note))
            answer['note']='코멘트 별지 '+str(len(comments))+'번 참조'
    summary=snapshot['data'].get('summary','')
    if summary and (form=='law'or len(summary)>240 or len(summary.splitlines())>6):
        comments.append(('총평',summary));snapshot['data']['summary']='총평 별지 참조'
    if form=='report':body,css=pptx(exports.pptx(snapshot,site,snapshot['inspector'],[],period,blind=blind))
    elif form=='law':body,css=hwpx(exports.hwpx(snapshot,site,snapshot['inspector']))
    else:body,css=xlsx(exports.xlsx(form,snapshot,site,snapshot['inspector']),snapshot.get('site_manager',''))
    if form=='report'and not blind:
        from .report_radar import page
        graph,styles=page(snapshot,site);end=body.find('</article>')+len('</article>');body=body[:end]+graph+body[end:];css+=styles
    if comments:
        body+='<article class="comment-appendix"><h1>'+safe(FORMS[form]['title'])+' 코멘트</h1><p>'+safe(site)+' · '+safe(snapshot['data']['inspection_date'])+'</p>'+''.join('<section><h2>'+safe(title)+'</h2><p>'+safe(note)+'</p></section>'for title,note in comments)+'</article>'
        css+='@page comments{size:A4 portrait;margin:16mm}.comment-appendix{page:comments;break-before:page;font-size:11pt;line-height:1.7}.comment-appendix h1{font-size:18pt}.comment-appendix h2{font-size:12pt;break-after:avoid;margin:7mm 0 2mm}.comment-appendix p{white-space:pre-wrap;overflow-wrap:anywhere;orphans:3;widows:3;margin:0 0 5mm}.comment-appendix section{break-inside:auto}'
    title=FORMS[form]['title']+' · '+site
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'"><title>'+escape(title)+'</title><style>*{box-sizing:border-box}body{margin:0;background:#fff;color:#111;font-family:"Malgun Gothic","Noto Sans CJK KR",sans-serif}table{border-collapse:collapse;table-layout:fixed;width:100%}td{border:.2mm solid #333;vertical-align:middle;overflow-wrap:anywhere}'+css+'@media screen{body{background:#e5e7eb}article{background:#fff;margin:12px auto;box-shadow:0 1px 5px #777}}@media print{article:last-child{break-after:auto}} </style>'+body+'</html>'
