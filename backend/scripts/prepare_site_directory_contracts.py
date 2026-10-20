"""Read only approved NAS contract folders; publish amounts without raw files.

The private folder map is reviewed before use. Latest amendments replace earlier
stages of one contract; separate contracts are added only once. Unknown scanned
contracts stay visible and prevent a partial sum being labelled a site total.
"""
from pathlib import Path
import argparse,collections,hashlib,html,json,re
import fitz

def sha(raw):return hashlib.sha256(raw).hexdigest()
def compact(value):return re.sub(r'\s+',' ',value).strip()
def money_after(label,body):
 m=re.search(label+r'\s*[:：]?[^￦₩\d]{0,90}[￦₩\\]?\s*([\d,]{5,})',body)
 if not m:return None
 value=int(m[1].replace(',',''))
 return value if 0<=value<1_000_000_000_000 else None
def amounts(body):
 body=compact(body)
 net=money_after(r'공\s*급\s*(?:가\s*액|금\s*액)',body)
 total=money_after(r'계\s*약\s*금\s*액',body) or money_after(r'도\s*급\s*금\s*액',body)
 tax=money_after(r'부\s*가\s*(?:가\s*치\s*)?세',body)
 if net and (not total or net<=total):return net,'VAT 별도'
 if total and tax is not None and 0<=tax<total:return total-tax,'VAT 별도'
 if total and re.search(r'(?:VAT|부가세|부가가치세)\s*(?:별도|별\s*도)',body,re.I):return total,'VAT 별도'
 return (total,'VAT 포함' if re.search(r'(?:VAT|부가세|부가가치세)\s*포함',body,re.I) else 'VAT 구분 미확인') if total else (None,'VAT 구분 미확인')
def text(raw,suffix):
 if suffix=='.pdf':
  with fitz.open(stream=raw,filetype='pdf') as doc:return '\n'.join(doc[i].get_text() for i in range(min(5,len(doc))))
 for encoding in ['utf-8-sig','cp949','utf-16']:
  try:body=raw.decode(encoding);break
  except UnicodeError:continue
 else:return ''
 return html.unescape(re.sub(r'<[^>]+>',' ',body))
def identity(group):
 name=group.name
 if ' - ' in name:name=name.split(' - ',1)[1]
 else:
  name=re.sub(r'^\d+(?:-\d+)?\.\s*','',name)
  name=re.sub(r'^(?:제?\d+\s*[차회]\s*)?(?:(?:당초|최초|변경|승계|정산|하도급|계약서|계약)\s*)+','',name)
 name=re.sub(r'[^가-힣A-Za-z0-9]','',name)
 name=re.sub(r'(?:발주처|원사업자|보증금율|구입사양서|내역서수정).*','',name)
 name=re.sub(r'^(?:제?\d+[차회])','',name)
 name=re.sub(r'(?:계약서|계약|공사)$','',name)
 name=name.replace('구내가설전기','구내가설').replace('가설전기','가설').replace('가설공사','가설')
 if name in {'전기설비','전기','일반전기','본공사'}:name='전기'
 if name in {'통신설비','통신'}:name='통신'
 if name in {'전기소방','소방전기','소방'}:name='소방'
 return name or '기본계약'
def stage(path):
 ranks=[int(x) for x in re.findall(r'(\d+)\s*[차회]\s*변경',str(path))]
 return max(ranks,default=1 if any(x in str(path) for x in ['변경계약','차변경','승계']) else 0)
def period(body):
 result=[]
 for label in [r'착\s*공',r'준\s*공']:
  m=re.search(label+r'\s*[:：]?\s*(20\d{2})\D{1,4}(\d{1,2})\D{1,4}(\d{1,2})',body)
  result.append('-'.join([m[1],m[2].zfill(2),m[3].zfill(2)]) if m else '')
 return result
def summarize(folder,evidence,errors):
 contracts=collections.defaultdict(list)
 for row in evidence:
  p=Path(row['path']);relative=p.relative_to(folder);group=Path(relative.parts[1]) if len(relative.parts)>2 else Path(relative.parts[0])
  if any(k in str(p) for k in ['적정성검토','시첨부서류','클린페이']):continue
  contracts[identity(group)].append(row)
 selected=[]
 for key,rows in contracts.items():
  latest_stage=max(r['stage'] for r in rows);latest=[r for r in rows if r['stage']==latest_stage]
  good=[r for r in latest if r['amount']]
  distinct={(r['amount'],r['basis']) for r in good}
  chosen=max(good or latest,key=lambda r:r['mtime'])
  if len(distinct)>1:chosen={**chosen,'amount':None,'conflict':True}
  selected.append({'key':key,'name':key,'amount':chosen['amount'],'basis':chosen['basis'],'start':chosen['start'],'end':chosen['end'],'stage':latest_stage,'source_sha256':chosen['sha256']})
 complete=bool(selected) and all(c['amount'] and c['basis']=='VAT 별도' for c in selected) and not errors
 total=sum(c['amount'] or 0 for c in selected if c['basis']=='VAT 별도')
 return {'contracts':selected,'total':total if complete else None,'confirmed_subtotal':total,'complete':complete,'basis':'VAT 별도','status':'미계약' if '미계약' in folder.name else '확인' if complete else '일부 확인' if selected else '계약금액 미확인'}

def parse(folder,manual):
 evidence=[];errors=[]
 roots=[p for p in folder.iterdir() if p.is_dir() and '계약서' in p.name and '자재' not in p.name]
 for root in roots:
  groups=[p for p in root.iterdir() if p.is_dir()] or [root]
  for group in groups:
   for p in group.rglob('*'):
    if not p.is_file() or p.suffix.lower() not in {'.pdf','.html','.htm'} or p.name.startswith('~$'):continue
    if not re.search(r'계약|게약|contract|agreement',p.name,re.I):continue
    if any(x in p.name for x in ['보증','인지','보험','특약','서약','일반조건','현장설명','신청서','내역서','예산','자재']):continue
    try:
     raw=p.read_bytes();digest=sha(raw);body=text(raw,p.suffix.lower());amount,basis=amounts(body);start,end=period(body)
     assert digest==sha(p.read_bytes()),'contract changed during read'
    except Exception as error:errors.append({'path':str(p),'error':type(error).__name__});continue
    verified=manual.get(str(p))
    if verified:
     assert verified['sha256']==digest
     amount=verified['amount'];basis=verified['basis'];start=verified.get('start',start);end=verified.get('end',end)
    row={'path':str(p),'sha256':digest,'amount':amount,'basis':basis,'stage':stage(p),'mtime':p.stat().st_mtime,'start':start,'end':end,'manual_visual':bool(verified)}
    evidence.append(row)
 return summarize(folder,evidence,errors),evidence,errors
def main(args):
 data=json.loads(args.input.read_text(encoding='utf-8'));mapping=json.loads(args.folders.read_text(encoding='utf-8'));manual=json.loads(args.manual.read_text(encoding='utf-8'));report=[]
 for s in data['sites']:
  folder=mapping.get(s['code'])
  if not folder:continue
  folder=Path(folder);assert folder.is_relative_to(Path(r'Z:\1. 원가관리팀 - 현장 계약 및 원가'))
  info,evidence,errors=parse(folder,manual);s['contract_info']=info
  report.append({'code':s['code'],'folder':str(folder),'info':info,'sources':evidence,'errors':errors})
  args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'code':s['code'],'contracts':len(info['contracts']),'complete':info['complete'],'errors':len(errors)}),flush=True)
 data['source']['contracts_as_of']='2026-10-20';data['version']='2026.10.20.4'
 args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for key in ['input','folders','manual','output','report']:p.add_argument('--'+key,required=True,type=Path)
 main(p.parse_args())
