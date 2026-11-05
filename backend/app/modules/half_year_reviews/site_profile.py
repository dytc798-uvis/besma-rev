"""Exact site identity and role based print defaults; never infer actual progress."""
from pathlib import Path
from copy import deepcopy
import json,re
from app.modules.inspection_reports.site_identity import resolve_sources,directory_snapshot,name_for,normalized

def facts():return json.loads(Path(__file__).with_name('site_profile_facts.json').read_text(encoding='utf8'))
def unique(values):return list(dict.fromkeys(str(v).strip()for v in values if v is not None and str(v).strip()))
def joined(values):return ' / '.join(unique(values))

def resolve(db,row,overrides=None):
    sources=resolve_sources(db,row);directory={s['code']:s for s in directory_snapshot().get('sites',[])};f=facts();managers=[];safety=[];contractors=[];trades=[];amounts=[];complete=bool(sources);seen_contracts=set();visit_contacts=[];visit_addresses=[]
    for site in sources:
        item=directory.get(site.site_code,{});erp=item.get('erp',{});current=f['sites'].get(site.site_code,{})
        contacts=item.get('contacts',[]);visit_addresses.append(item.get('address')or getattr(site,'address',None))
        for contact in contacts:
            allowed={k:str(contact.get(k)or'').strip()for k in ['name','role','phone','rank','label']}
            if allowed not in visit_contacts:visit_contacts.append(allowed)
        role_names=[c.get('name')for c in contacts if '소장'in c.get('role','')]
        # Site.site_manager historically contains a clerk on several contracts.
        managers.extend(unique([current.get('manager')]or role_names)if current.get('manager')else unique(role_names or [getattr(site,'manager_name',None)]))
        safety.extend(c.get('name')for c in contacts if '안전'in c.get('role',''))
        contractors.append(current.get('contractor')or erp.get('contractor')or getattr(site,'contractor_name',None));trades.append(current.get('trade')or erp.get('work_types')or getattr(site,'work_types',None))
        info=item.get('contract_info',{});entries=info.get('contracts',[])
        if entries:
            complete=complete and info.get('complete',False)
            for contract in entries:
                key=contract.get('key')or(site.site_code,contract.get('name'))
                if key in seen_contracts:continue
                seen_contracts.add(key)
                value=contract.get('amount')
                if isinstance(value,(int,float))and value>0:amounts.append((contract.get('name',''),value,contract.get('basis','')))
        else:
            value=current.get('amount')or erp.get('amount')or getattr(site,'project_amount',None)
            if isinstance(value,(int,float))and value>0:amounts.append(('',value,''))
            else:complete=False
    names=unique(managers)
    amount=(f'{sum(x[1]for x in amounts):,.0f}원'+(' (VAT 별도)'if all('별도'in x[2]for x in amounts)else''))if amounts and complete else joined((name+' 'if name else'')+f'{value:,.0f}원'+(' (VAT 별도)'if '별도'in basis else'')for name,value,basis in amounts)
    if amounts and not complete:amount+=' (일부 계약금액)'
    progress='';as_of='';p=f.get('progress',{}).get(row.client_item_key,{})
    if p and normalized(p.get('site'))==normalized(name_for(row)):
        progress=f'{p["value"]*100:g}%';as_of=p.get('date')or''
    result={'site_manager':joined(names),'manager_default':names[0]if len(names)==1 else'','safety_staff':joined(safety),'contractor':joined(contractors),'trade':joined(trades),'construction_amount':amount,'progress':progress,'progress_date':as_of}
    result['visit_contacts']=visit_contacts;result['visit_address']=joined(visit_addresses)
    for k,v in (overrides or{}).items():
        if k in FIELDS:result[k]=v
    if 'site_manager'in(overrides or{}):result['manager_default']=result['site_manager']if len(result['site_manager'])<=40 else''
    return result

FIELDS={'site_manager':80,'safety_staff':160,'contractor':200,'trade':120,'construction_amount':200,'progress':20,'progress_date':10}
def validate_details(body):
    from .catalog import cleaned
    from datetime import date
    if not isinstance(body,dict)or not body or set(body)-set(FIELDS):raise ValueError('SITE_DETAILS_INVALID')
    out={k:cleaned(v,FIELDS[k])for k,v in body.items()}
    if out.get('progress'):
        if not re.fullmatch(r'(?:\d{1,3})(?:\.\d+)?%?',out['progress'])or not 0<=float(out['progress'].rstrip('%'))<=100:raise ValueError('SITE_DETAILS_INVALID')
        out['progress']=out['progress'].rstrip('%')+'%'
    if out.get('progress_date'):date.fromisoformat(out['progress_date'])
    return out

def enrich(snapshot,profile,assessment=None):
    """Print a copy; completed evidence and grades remain immutable."""
    value=deepcopy(snapshot);value.update(profile)
    draft=(assessment or{}).get('draft')
    if draft and draft.get('data',{}).get('inspection_date')==value['data'].get('inspection_date'):
        old=value['data']['answers'];new=draft['data']['answers']
        # Later saved prose is printable only with the same evaluated grades.
        if set(old)==set(new)and all(old[k].get('value')==new[k].get('value')for k in old):
            value['data']['summary']=draft['data'].get('summary','')
            value['data']['improvements']=deepcopy(draft['data'].get('improvements',[]))
            for k in old:old[k]['note']=new[k].get('note','')
    if value.get('form')=='manager'and not value.get('subject_name'):value['subject_name']=profile.get('manager_default','')
    return value
