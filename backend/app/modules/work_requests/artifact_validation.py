"""Validate generated PDF bytes before private publication; no source mutation."""
from io import BytesIO
import re,unicodedata

PDF_PREFIX='파일 형식: PDF\n'

def pdf_name(title):
    value=re.sub(r'[\\/:*?"<>|\x00-\x1f]',' ',unicodedata.normalize('NFC',title))
    value=' '.join(value.split()).strip(' .')[:100].rstrip(' .')or'요청자료'
    if re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',value.split('.')[0]):value='자료 '+value
    return value+'.pdf'

def validate_pdf(content):
    from pypdf import PdfReader
    if not isinstance(content,bytes)or not content.startswith(b'%PDF-')or b'%%EOF'not in content[-1024:]:raise ValueError('GENERATED_PDF_REQUIRED')
    try:
        reader=PdfReader(BytesIO(content),strict=True)
        if reader.is_encrypted or not 1<=len(reader.pages)<=20:raise ValueError('GENERATED_PDF_INVALID')
        root=reader.trailer['/Root']
        if any(k in root for k in ['/OpenAction','/AA','/AcroForm','/Collection'])or root.get('/Names'):raise ValueError('GENERATED_PDF_ACTIVE_CONTENT')
        if any(page.get('/Annots')or page.get('/AA')for page in reader.pages):raise ValueError('GENERATED_PDF_ACTIVE_CONTENT')
        if not ''.join(page.extract_text()or''for page in reader.pages).strip():raise ValueError('GENERATED_PDF_TEXT_REQUIRED')
    except ValueError:raise
    except Exception as error:raise ValueError('GENERATED_PDF_INVALID')from error


def edited_name(source_name):
    from pathlib import Path
    p=Path(source_name)
    if p.name!=source_name or p.suffix.lower()not in {'.txt','.docx','.xlsx'}:raise ValueError('SOURCE_EDIT_FORMAT_REQUIRED')
    return p.stem[:200]+'_수정안'+p.suffix


def validate_edited_copy(source_name,filename,content):
    import stat,zipfile
    from pathlib import Path
    from xml.etree import ElementTree as ET
    if filename!=edited_name(source_name)or not isinstance(content,bytes)or not 0<len(content)<=16*1024*1024:raise ValueError('SOURCE_EDIT_COPY_REQUIRED')
    if Path(filename).suffix.lower()=='.txt':
        try:
            if content.startswith((b'\xff\xfe',b'\xfe\xff')):text=content.decode('utf-16')
            else:
                try:text=content.decode('utf-8-sig')
                except UnicodeDecodeError:text=content.decode('cp949')
            if not text.strip()or '\x00'in text:raise ValueError('SOURCE_EDIT_TEXT_INVALID')
        except UnicodeError as error:raise ValueError('SOURCE_EDIT_TEXT_INVALID')from error
        return
    try:
        with zipfile.ZipFile(BytesIO(content))as z:
            infos=z.infolist();names=z.namelist()
            if len(infos)>1000 or len(names)!=len(set(n.casefold()for n in names))or sum(i.file_size for i in infos)>32*1024*1024:raise ValueError('SOURCE_EDIT_PACKAGE_INVALID')
            if any(i.flag_bits&1 or i.compress_type not in {0,8}or stat.S_ISLNK(i.external_attr>>16)or i.file_size>8*1024*1024 for i in infos):raise ValueError('SOURCE_EDIT_PACKAGE_INVALID')
            if any(n.startswith('/')or'\\'in n or':'in n or any(p in {'.','..'}for p in n.split('/'))or n.casefold().startswith(('_xmlsignatures/','word/activex/','word/embeddings/'))or n.casefold().endswith('vbaproject.bin')for n in names):raise ValueError('SOURCE_EDIT_PACKAGE_INVALID')
            if '[Content_Types].xml'not in names:raise ValueError('SOURCE_EDIT_PACKAGE_INVALID')
            workbook=Path(filename).suffix.lower()=='.xlsx'
            if workbook and any(n.casefold().startswith(('xl/activex/','xl/embeddings/','xl/externallinks/'))for n in names):raise ValueError('SOURCE_EDIT_PACKAGE_INVALID')
            body=z.read('xl/workbook.xml'if workbook else'word/document.xml')
            if b'<!DOCTYPE'in body.upper()or b'<!ENTITY'in body.upper():raise ValueError('SOURCE_EDIT_PACKAGE_INVALID')
            root=ET.fromstring(body)
            if root.tag!=('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook'if workbook else'{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document'):raise ValueError('SOURCE_EDIT_PACKAGE_INVALID')
    except ValueError:raise
    except Exception as error:raise ValueError('SOURCE_EDIT_PACKAGE_INVALID')from error
