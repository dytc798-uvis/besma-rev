"""Existing review events bind source-based output mode. No new authorization grant."""
from .artifact_validation import pdf_name,validate_pdf
FORMATS={'TXT','PDF'}
def requested(connection,row):
 if row['kind']!='FILE'or not row['source_json']:return None
 found={r['status'].split(':',1)[1]for r in connection.execute("SELECT status FROM events WHERE request_id=? AND status IN ('LOOKUP_ACTION_CREATE:TXT','LOOKUP_ACTION_CREATE:PDF')",(row['id'],))}
 if len(found)>1:raise ValueError('AMBIGUOUS_SOURCE_GENERATION_FORMAT')
 return next(iter(found),None)
def name(title,format):
 if format not in FORMATS:raise ValueError('SOURCE_GENERATION_FORMAT_REQUIRED')
 return pdf_name(title)if format=='PDF'else pdf_name(title)[:-4]+'.txt'
def validate(title,format,filename,content):
 if filename!=name(title,format)or not isinstance(content,bytes)or not 0<len(content)<=16*1024*1024:raise ValueError('EXACT_SOURCE_GENERATION_COPY_REQUIRED')
 if format=='PDF':validate_pdf(content)
 else:
  try:text=content.decode('utf-8-sig')
  except UnicodeError:raise ValueError('GENERATED_UTF8_TEXT_REQUIRED')from None
  if not text.strip()or len(text)>200000 or '\x00'in text:raise ValueError('GENERATED_TEXT_REQUIRED')
