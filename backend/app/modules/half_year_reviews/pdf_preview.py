"""Read-only reduced previews of an already-authorized, hash-checked PDF."""
from contextlib import contextmanager
import hashlib,math

MAX_BYTES=15*1024*1024
MAX_PAGES=100
LONG_EDGE=1400

@contextmanager
def document(raw):
    import fitz
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES or not raw.startswith(b'%PDF-'):
        raise ValueError('PDF_PREVIEW_UNAVAILABLE')
    doc=None
    try:
        doc=fitz.open(stream=raw,filetype='pdf')
        if doc.needs_pass or not 1<=len(doc)<=MAX_PAGES:raise ValueError('PDF_PREVIEW_UNAVAILABLE')
        for page in doc:
            if not all(math.isfinite(v)and 30<=v<=3000 for v in [page.rect.width,page.rect.height]):raise ValueError('PDF_PREVIEW_UNAVAILABLE')
    except Exception:
        if doc is not None:doc.close()
        raise ValueError('PDF_PREVIEW_UNAVAILABLE')from None
    try:yield doc
    finally:doc.close()

def information(raw,meta):
    if meta.get('extension')!='.pdf':raise ValueError('PDF_PREVIEW_UNAVAILABLE')
    if len(raw)!=meta.get('bytes')or hashlib.sha256(raw).hexdigest()!=meta.get('sha256'):raise ValueError('PDF_PREVIEW_SOURCE_CHANGED')
    with document(raw)as doc:
        return {'source_sha256':meta['sha256'],'source_bytes':meta['bytes'],'pages':[{'number':i+1,'width':page.rect.width,'height':page.rect.height}for i,page in enumerate(doc)],'preview_long_edge':LONG_EDGE}

def render(raw,meta,number):
    import fitz
    if meta.get('extension')!='.pdf':raise ValueError('PDF_PREVIEW_UNAVAILABLE')
    if len(raw)!=meta.get('bytes')or hashlib.sha256(raw).hexdigest()!=meta.get('sha256'):raise ValueError('PDF_PREVIEW_SOURCE_CHANGED')
    with document(raw)as doc:
        if type(number)is not int or not 1<=number<=len(doc):raise KeyError('PDF_PREVIEW_PAGE_MISSING')
        page=doc[number-1];zoom=min(1.7,(LONG_EDGE-1)/max(page.rect.width,page.rect.height));pixmap=page.get_pixmap(matrix=fitz.Matrix(zoom,zoom),alpha=False)
        if max(pixmap.width,pixmap.height)>LONG_EDGE:raise ValueError('PDF_PREVIEW_UNAVAILABLE')
        data=pixmap.tobytes('png')
        if not 0<len(data)<=6*1024*1024:raise ValueError('PDF_PREVIEW_UNAVAILABLE')
        return data,{'source_sha256':meta['sha256'],'page_number':number,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
