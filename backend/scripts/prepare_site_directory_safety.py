"""Merge purpose-limited safety contacts into a private directory snapshot.

Raw ERP columns outside name, role, site, employment dates and phone are never
projected. NAS current assignments take precedence over older daily registrations.
The output and reconciliation report contain personal data and must stay private.
"""
import argparse,collections,datetime,hashlib,io,json,re
from pathlib import Path
import olefile,openpyxl,xlrd

def normalize(value):return re.sub(r'\s+','',str(value or '')).strip()
def phone(value):
 digits=re.sub(r'\D','',str(value or ''))
 return digits[:3]+'-'+digits[3:-4]+'-'+digits[-4:] if re.fullmatch(r'01[016789]\d{7,8}',digits) else ''
def read_xls(path):
 with olefile.OleFileIO(path) as ole:
  return xlrd.open_workbook(file_contents=ole.openstream('Workbook').read(),logfile=io.StringIO()).sheet_by_index(0)
def text(sheet,row,col):
 value=sheet.cell_value(row,col)
 return str(int(value)) if sheet.cell_type(row,col)==xlrd.XL_CELL_NUMBER else str(value).strip()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def merge(args):
 inputs=[args.baseline,args.employees,args.daily,args.appointments,args.nas_contacts,args.overrides,args.confirmed]
 hashes={str(p):sha(p) for p in inputs}
 data=load(args.baseline);sites={s['code']:s for s in data['sites']}
 bysite=collections.defaultdict(list)
 for s in sites.values():bysite[normalize(s['name'])].append(s['code'])
 def site_code(code,name):
  code=normalize(code)
  if code in sites:return code
  codes=bysite.get(normalize(name),[])
  return codes[0] if len(codes)==1 else ''
 s=read_xls(args.employees)
 assert normalize(text(s,0,0))=='성명' and text(s,0,5)=='직위' and text(s,0,18)=='휴대폰'
 legend=dict(re.findall(r'^(\d+)\.([^\r\n]+)',text(s,s.nrows-1,5),re.M))
 rank_labels={'사원','대리','과장','차장','부장','상무','대표','부사장','전무','상임고문','이사','실장'}
 employees=collections.defaultdict(list)
 for i in range(1,s.nrows-1):
  if text(s,i,21):continue
  name=normalize(text(s,i,0));number=phone(''.join(text(s,i,c) for c in [18,19,20])) or phone(''.join(text(s,i,c) for c in [15,16,17]))
  rank=legend.get(text(s,i,5),'').removeprefix('공무')
  if name:employees[name].append({'name':name,'phone':number,'rank':rank if rank in rank_labels else ''})
 daily=[];s=read_xls(args.daily)
 assert normalize(text(s,0,0))=='성명' and text(s,0,6)=='직종' and text(s,0,7)=='소속현장코드' and text(s,0,10)=='휴대폰'
 for i in range(1,s.nrows-1):
  if text(s,i,4):continue
  name=normalize(text(s,i,0));code=text(s,i,7)
  if name:daily.append({'name':name,'phone':phone(text(s,i,10)) or phone(text(s,i,11)),'code':code,'occupation':text(s,i,6),'rank':''})
 edits=load(args.overrides)['People']
 nas_phones=collections.defaultdict(set)
 w=openpyxl.load_workbook(args.nas_contacts,read_only=True,data_only=True)
 for r in w.worksheets[0].iter_rows(min_row=3,values_only=True):
  if r[2] and phone(r[3]):nas_phones[(site_code('',r[0]),normalize(r[2]))].add(phone(r[3]))
 w.close()
 assignments=[];unresolved=[];completed=set();nas_byname=collections.defaultdict(set)
 w=openpyxl.load_workbook(args.appointments,read_only=True,data_only=True);s=w['안전관리자']
 assert s.cell(4,3).value=='이름' and s.cell(4,27).value=='현장코드'
 for i,r in enumerate(s.iter_rows(min_row=5,values_only=True),5):
  name=normalize(r[2]);code=site_code(r[26],r[0]);status=normalize(r[11]);dismissed=r[19]
  if not name:continue
  if status in {'준공','해임'} or dismissed:
   if code:completed.add((code,name))
   continue
  if not code:unresolved.append({'name':name,'site':str(r[0]),'reason':'site_not_resolved','nas_row':i});continue
  assignments.append({'name':name,'code':code,'role':'안전','source':'NAS105','nas_row':i})
  nas_byname[name].add(code)
 w.close()
 # Daily occupation 42 is the safety-manager registration. It also includes
 # additional staff omitted from the NAS sheet. Never import the whole workforce.
 for r in daily:
  if r['code'] not in sites or r['occupation']!='42' or (r['code'],r['name']) in completed:continue
  if nas_byname[r['name']] and r['code'] not in nas_byname[r['name']]:continue
  assignments.append({**r,'role':'안전','source':'daily_safety'})
 # Individually confirmed non-safety staff are explicit private input, not code.
 for r in load(args.confirmed):assignments.append({**r,'source':'user_confirmed'})
 evidence=[];added=0;updated=0
 for a in assignments:
  name,code=a['name'],a['code'];edit=edits.get(name,{})
  if edit.get('SiteCode')=='' and edit.get('Site') in {'본사','본사 안전보건실'}:
   unresolved.append({**a,'reason':'explicit_hq_override'});continue
  candidates=[r for r in daily if r['name']==name and r['code']==code]
  numbers={r['phone'] for r in candidates if r['phone']}
  emps=employees.get(name,[])
  if not numbers and len(emps)==1 and emps[0]['phone']:numbers.add(emps[0]['phone'])
  if not numbers:numbers=nas_phones.get((code,name),set())
  # Current NAS assignment may precede an ERP transfer. Accept another site's
  # registration only when this name resolves to one unique phone globally.
  if not numbers and a['source']=='NAS105':
   fallback={r['phone'] for r in daily if r['name']==name and r['phone']}
   if len(fallback)==1:numbers=fallback;a['phone_source']='unique_name_registration_current_nas_site'
  if len(numbers)!=1:
   unresolved.append({**a,'reason':'ambiguous_phone' if numbers else 'missing_phone'});continue
  number=next(iter(numbers));rank=''
  if len(emps)==1 and (not emps[0]['phone'] or emps[0]['phone']==number):rank=emps[0]['rank']
  if edit.get('SiteCode')==code and len(emps)==1 and emps[0]['phone']==number:
   rank=edit.get('Rank',rank) or rank
   if edit.get('Phone'):number=phone(edit['Phone'])
  role=a['role'];existing=[c for c in sites[code]['contacts'] if c['name']==name and c['phone']==number]
  # Preserve manager/engineering role and show an additional confirmed safety duty.
  current=next(iter(existing),None)
  if current and current.get('rank'):rank=current['rank']
  duties=list(dict.fromkeys((current['role'].split('·') if current else [])+[role]))
  label=name+('소장' if '소장' in duties else rank)
  if duties!=['소장']:label+='('+ '·'.join(duties)+')'
  elif role!='소장':label+='('+role+')'
  contact={'name':name,'rank':rank,'role':'·'.join(duties),'label':label,'phone':number,'rank_confirmed':bool(rank) or '소장' in duties}
  if current:
   if current!=contact:sites[code]['contacts'][sites[code]['contacts'].index(current)]=contact;updated+=1
  else:sites[code]['contacts'].append(contact);added+=1
  evidence.append({**a,'phone_resolved':True,'rank_confirmed':bool(rank)})
 # Keep identified safety staff visible even where no source contains a phone.
 # A missing number must never silently erase a NAS safety assignment.
 for a in unresolved:
  if a['reason'] not in {'missing_phone','ambiguous_phone'}:continue
  if any(c['name']==a['name'] for c in sites[a['code']]['contacts']):continue
  sites[a['code']]['contacts'].append({'name':a['name'],'rank':'','role':a['role'],'label':a['name']+'('+a['role']+')','phone':'','rank_confirmed':False,'phone_status':a['reason']})
  added+=1
 for site in sites.values():
  keys=[(c['name'],c['phone']) for c in site['contacts']]
  assert len(keys)==len(set(keys))
 data['version']='2026.10.20.4'
 data['source'].update(safety_assignments_as_of='2026-10-20',daily_registration_as_of='2026-10-15',employee_registration_as_of='2026-10-19')
 # Stable read: never publish against a workbook changed while being reconciled.
 assert hashes=={str(p):sha(p) for p in inputs},'Source changed during reconciliation'
 Path(args.output).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 report={'source_hashes':hashes,'version':data['version'],'added':added,'updated':updated,'sites':len(sites),'contacts':sum(len(s['contacts']) for s in sites.values()),'sites_with_contacts':sum(bool(s['contacts']) for s in sites.values()),'evidence':evidence,'unresolved':unresolved,'output_sha256':sha(args.output)}
 Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for key in ['baseline','employees','daily','appointments','nas-contacts','overrides','confirmed','output','report']:p.add_argument('--'+key,required=True,type=Path)
 r=merge(p.parse_args());print(json.dumps({k:v for k,v in r.items() if k not in {'source_hashes','evidence','unresolved'}},ensure_ascii=False));print('unresolved',len(r['unresolved']))
