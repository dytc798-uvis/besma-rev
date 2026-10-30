"""Fill the pinned user template without rebuilding its layouts or theme."""
from copy import deepcopy
from datetime import date,timedelta
import hashlib,io,math,re,zipfile
from xml.etree import ElementTree as E
from PIL import Image,ImageOps,UnidentifiedImageError

TEMPLATE_SHA256='34d870f4bb9b33c63c6c3c05b0bb67410126066ed2b7aa866801829d7521482d'
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
for prefix,uri in NS.items():E.register_namespace(prefix,uri)
def q(prefix,name):return '{'+NS[prefix]+'}'+name
def xml(root):return E.tostring(root,encoding='utf-8',xml_declaration=True)
def text(node,value):
    runs=node.findall('.//a:t',NS)
    if not runs:
        paragraph=node.find('.//a:p',NS)
        if paragraph is None:raise ValueError('TEMPLATE_TEXT_SLOT_MISSING')
        run=E.SubElement(paragraph,q('a','r'))
        ending=paragraph.find('a:endParaRPr',NS)
        if ending is not None:
            style=deepcopy(ending);style.tag=q('a','rPr');run.append(style)
        runs=[E.SubElement(run,q('a','t'))]
    for i,run in enumerate(runs):run.text=str(value)if i==0 else''
def shape(root,ident):
    for item in root.find('p:cSld/p:spTree',NS):
        prop=item.find('.//p:cNvPr',NS)
        if prop is not None and prop.get('id')==str(ident):return item
    raise ValueError('TEMPLATE_SHAPE_MISSING')
def cell(root,ident,row,col):return shape(root,ident).findall('.//a:tr',NS)[row].findall('a:tc',NS)[col]

def normalize_photo(raw):
    if not raw or len(raw)>15*1024*1024:raise ValueError('PHOTO_SIZE_INVALID')
    try:
        with Image.open(io.BytesIO(raw))as source:
            if source.format not in {'JPEG','PNG','WEBP'}or source.width*source.height>50_000_000:raise ValueError('PHOTO_FORMAT_INVALID')
            image=ImageOps.exif_transpose(source);image.thumbnail((1600,1600),Image.Resampling.LANCZOS)
            if image.mode!='RGB':
                rgba=image.convert('RGBA');image=Image.new('RGB',rgba.size,'white');image.paste(rgba,mask=rgba.getchannel('A'))
            output=io.BytesIO();image.save(output,'JPEG',quality=84,optimize=True)
            data=output.getvalue()
            return {'data':data,'width':image.width,'height':image.height,'sha256':hashlib.sha256(data).hexdigest()}
    except(UnidentifiedImageError,OSError,Image.DecompressionBombError)as error:raise ValueError('PHOTO_INVALID')from error

def make_report(template,fields,photos):
    if hashlib.sha256(template).hexdigest()!=TEMPLATE_SHA256:raise ValueError('TEMPLATE_CHANGED')
    if not 1<=len(photos)<=24:raise ValueError('PHOTO_COUNT_INVALID')
    site=fields['site_name'];day=date.fromisoformat(fields['inspection_date'])
    if not isinstance(site,str)or not 1<=len(site)<=100:raise ValueError('SITE_NAME_INVALID')
    for value in [v for v in fields.values()if isinstance(v,str)]+[p.get('caption','')for p in photos]:
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',value):raise ValueError('TEXT_INVALID')
    if len(fields.get('summary',''))>240 or len(fields.get('summary','').splitlines())>6:raise ValueError('SUMMARY_TOO_LONG')
    for photo in photos:
        if len(photo.get('caption',''))>60 or len(photo.get('caption','').splitlines())>3:raise ValueError('PHOTO_CAPTION_TOO_LONG')
        if hashlib.sha256(photo['data']).hexdigest()!=photo['sha256']:raise ValueError('PHOTO_CHANGED')
    with zipfile.ZipFile(io.BytesIO(template))as z:parts={n:z.read(n)for n in z.namelist()}
    cover=E.fromstring(parts['ppt/slides/slide1.xml']);text(cell(cover,6,0,1),site);text(cell(cover,6,1,1),day.strftime('%Y.%m.%d'));text(shape(cover,5),f'{day.year}년 '+('상'if day.month<=6 else'하')+'반기');parts['ppt/slides/slide1.xml']=xml(cover)
    overview=E.fromstring(parts['ppt/slides/slide2.xml']);text(cell(overview,7,1,1),site);text(cell(overview,7,3,1),day.strftime('%Y.%m.%d'))
    for row,key in [(2,'contractor_trade'),(4,'site_manager'),(5,'inspector'),(6,'contract_progress')]:
        if fields.get(key):text(cell(overview,7,row,1),fields[key])
    parts['ppt/slides/slide2.xml']=xml(overview)
    confirm=E.fromstring(parts['ppt/slides/slide6.xml']);text(cell(confirm,7,0,1),site);text(cell(confirm,7,0,3),day.strftime('%Y.%m.%d'));text(cell(confirm,7,1,1),fields.get('evaluation_period')or f'{day.year}년 '+('상'if day.month<=6 else'하')+'반기')
    if fields.get('summary'):text(cell(confirm,9,0,0),fields['summary'])
    if fields.get('inspector'):text(cell(confirm,11,0,1),fields['inspector']+'  (서명)')
    if fields.get('site_manager'):text(cell(confirm,11,0,3),fields['site_manager']+'  (서명)')
    # Scores, approval/signature ink and the improvement table are not inferred.
    parts['ppt/slides/slide6.xml']=xml(confirm)
    presentation=E.fromstring(parts['ppt/presentation.xml']);ids=presentation.find('p:sldIdLst',NS);rels=E.fromstring(parts['ppt/_rels/presentation.xml.rels']);types=E.fromstring(parts['[Content_Types].xml'])
    if not any(x.get('Extension')=='jpg'for x in types):E.SubElement(types,'{'+CT+'}Default',{'Extension':'jpg','ContentType':'image/jpeg'})
    base_photo=parts['ppt/slides/slide5.xml'];base_rels=parts.get('ppt/slides/_rels/slide5.xml.rels',xml(E.Element('{'+REL+'}Relationships')))
    page_count=math.ceil(len(photos)/4);max_slide_id=max(int(x.get('id'))for x in ids)
    for page in range(page_count):
        root=E.fromstring(base_photo);slide_rels=E.fromstring(base_rels);tree=root.find('p:cSld/p:spTree',NS)
        if page:
            for rel in list(slide_rels):
                if rel.get('Type','').endswith('/notesSlide'):slide_rels.remove(rel)
        for slot,(frame_id,placeholder_id,caption_id)in enumerate([(7,8,9),(10,11,12),(13,14,15),(16,17,18)]):
            index=page*4+slot;tree.remove(shape(root,placeholder_id))
            if index>=len(photos):text(cell(root,caption_id,0,0),'');text(cell(root,caption_id,0,1),'');continue
            photo=photos[index];text(cell(root,caption_id,0,0),f'{index+1:02d}');text(cell(root,caption_id,0,1),photo.get('caption',''))
            frame=shape(root,frame_id).find('p:spPr/a:xfrm',NS);off=frame.find('a:off',NS);ext=frame.find('a:ext',NS);x,y,cx,cy=[int(v)for v in (off.get('x'),off.get('y'),ext.get('cx'),ext.get('cy'))]
            scale=min((cx-60000)/photo['width'],(cy-60000)/photo['height']);width=round(photo['width']*scale);height=round(photo['height']*scale)
            filename='inspection-'+photo['sha256']+'.jpg';parts['ppt/media/'+filename]=photo['data'];rid=f'rIdInspectionPhoto{slot+1}'
            E.SubElement(slide_rels,'{'+REL+'}Relationship',{'Id':rid,'Type':NS['r']+'/image','Target':'../media/'+filename})
            picture=E.Element(q('p','pic'));nv=E.SubElement(picture,q('p','nvPicPr'));E.SubElement(nv,q('p','cNvPr'),{'id':str(100+slot),'name':f'점검사진 {index+1:02d}'});E.SubElement(nv,q('p','cNvPicPr'));E.SubElement(nv,q('p','nvPr'))
            fill=E.SubElement(picture,q('p','blipFill'));E.SubElement(fill,q('a','blip'),{q('r','embed'):rid});stretch=E.SubElement(fill,q('a','stretch'));E.SubElement(stretch,q('a','fillRect'))
            props=E.SubElement(picture,q('p','spPr'));transform=E.SubElement(props,q('a','xfrm'));E.SubElement(transform,q('a','off'),{'x':str(x+(cx-width)//2),'y':str(y+(cy-height)//2)});E.SubElement(transform,q('a','ext'),{'cx':str(width),'cy':str(height)});geometry=E.SubElement(props,q('a','prstGeom'),{'prst':'rect'});E.SubElement(geometry,q('a','avLst'));tree.append(picture)
        number=5 if page==0 else 6+page
        if page:
            rid=f'rIdInspectionPage{page}';E.SubElement(rels,'{'+REL+'}Relationship',{'Id':rid,'Type':NS['r']+'/slide','Target':f'slides/slide{number}.xml'});ids.insert(4+page,E.Element(q('p','sldId'),{'id':str(max_slide_id+page),q('r','id'):rid}));E.SubElement(types,'{'+CT+'}Override',{'PartName':f'/ppt/slides/slide{number}.xml','ContentType':'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'})
            text(shape(root,6),f'04-{page+1}')
        parts[f'ppt/slides/slide{number}.xml']=xml(root);parts[f'ppt/slides/_rels/slide{number}.xml.rels']=xml(slide_rels)
    parts['ppt/presentation.xml']=xml(presentation);parts['ppt/_rels/presentation.xml.rels']=xml(rels);parts['[Content_Types].xml']=xml(types)
    if 'docProps/app.xml'in parts:
        app=E.fromstring(parts['docProps/app.xml'])
        for entry in app:
            if entry.tag.endswith('}Slides'):entry.text=str(6+page_count-1)
        parts['docProps/app.xml']=xml(app)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED)as z:
        for name,data in parts.items():z.writestr(name,data)
    return output.getvalue()
