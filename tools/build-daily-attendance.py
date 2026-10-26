"""Project allowed columns from an existing verified ERP export; raw identity stays in Downloads."""
import argparse,collections,datetime as dt,hashlib,io,json,re,os
from pathlib import Path
import olefile,xlrd
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def normalize(value):
    label=re.sub(r'^현장명\s*[:：]\s*','',str(value)).strip()
    return re.sub(r'[^가-힣a-z0-9]','',re.sub(r'^\[[^\]]+\]\s*','',label).lower())
def build(source,receipt,catalog):
    if sha(source)!=receipt['SourceSha256']:raise ValueError('SOURCE_HASH_MISMATCH')
    day=dt.date.fromisoformat(receipt['Date']);captured=dt.datetime.fromisoformat(receipt['CapturedAt'])
    if captured.astimezone(dt.timezone(dt.timedelta(hours=9))).date()!=day:raise ValueError('CAPTURE_DATE_MISMATCH')
    aliases=catalog.get('aliases',{}) if isinstance(catalog,dict) else {}
    catalog=catalog['sites'] if isinstance(catalog,dict) else catalog
    by_label=collections.defaultdict(set)
    for s in catalog:
        for field in ('site_name','name'):
            if s.get(field):
                code=s.get('site_code',s.get('code'));by_label[normalize(s[field])].add(aliases.get(code,code))
    with olefile.OleFileIO(source) as ole:
        sheet=xlrd.open_workbook(file_contents=ole.openstream('Workbook').read(),logfile=io.StringIO()).sheet_by_index(0)
    if sheet.ncols<15:raise ValueError('ERP_SCHEMA_CHANGED')
    header=False;section=None;label='';people={};counts=collections.Counter();unidentified=0
    for i in range(sheet.nrows):
        first=str(sheet.cell_value(i,0)).strip()
        if first.startswith('출역일:'):
            section=first.split(':',1)[1].strip();label=re.sub(r'^현장명\s*[:：]\s*','',str(sheet.cell_value(i,3))).strip()
            if section!=day.isoformat():raise ValueError('SOURCE_DATE_MISMATCH')
            continue
        if first=='성명':
            if str(sheet.cell_value(i,7)).strip()!='합계':raise ValueError('ERP_HEADER_CHANGED')
            header=True;continue
        if not first or first in {'일출역현황','합계','소계','총계'}:continue
        try:positive=float(sheet.cell_value(i,7))>0
        except (ValueError,TypeError):continue
        if not positive:continue
        if not section:raise ValueError('MISSING_SECTION_DATE')
        ids=by_label.get(normalize(label),set());code=next(iter(ids)) if len(ids)==1 else None
        rrn=re.sub(r'\D','',str(sheet.cell_value(i,1)))
        if len(rrn)==13:
            identity=hashlib.sha256(rrn.encode()).hexdigest()
        else:
            identity='unidentified-'+str(i);unidentified+=1
        if identity in people:continue
        people[identity]={'rrn_hash':identity if len(rrn)==13 else None,'site_code':code}
        counts[(code,label)]+=1
    if not header or len(people)!=receipt['People']:raise ValueError('RECEIPT_COUNT_MISMATCH')
    return {'schema':1,'date':day.isoformat(),'captured_at':receipt['CapturedAt'],'source_sha256':sha(source),'source_filename':source.name,'people':len(people),'unidentified_people':unidentified,'sites':[{'code':code,'name':name,'people':count} for (code,name),count in counts.items()],'identities':list(people.values())}
def main():
    p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    receipt=json.loads(a.receipt.read_text(encoding='utf-8-sig'));expected=receipt['SourceSha256']
    matches=[x for x in (Path.home()/'Downloads').glob('출역일보*.xls') if sha(x)==expected]
    if len(matches)!=1:raise ValueError('EXACT_SOURCE_NOT_FOUND')
    catalog=json.loads(a.catalog.read_text(encoding='utf-8-sig'))
    result=build(matches[0],receipt,catalog);a.out.parent.mkdir(parents=True,exist_ok=True)
    if a.out.exists() and a.out.read_text(encoding='utf-8')==json.dumps(result,ensure_ascii=False,separators=(',',':')):return
    tmp=a.out.with_suffix('.new');tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8');os.replace(tmp,a.out)
    print(json.dumps({'date':result['date'],'people':result['people'],'sites':len(result['sites']),'unmatched_site_people':sum(s['people'] for s in result['sites'] if s['code'] is None),'unidentified_people':result['unidentified_people']},ensure_ascii=True))
if __name__=='__main__':main()
