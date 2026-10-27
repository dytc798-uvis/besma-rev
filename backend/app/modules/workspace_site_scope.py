"""Display scope only; contract, attendance and evaluation records stay intact."""
import re

def annual_unit_contract(site):
    name=str(site.get('name') or site.get('site_name') or '')
    compact=re.sub(r'\s+','',name)
    # ERP directory titles explicitly mark the annual contract group in brackets.
    if re.search(r'\[[^\]]*[-－–—]연간\]',compact):return True
    if '연간단가' in re.sub(r'[^가-힣A-Za-z0-9]','',compact):return True
    kinds=[site.get('contract_type')]
    kinds.extend(d.get('value') for d in site.get('details',[]) if d.get('key')=='contract_type')
    for raw in kinds:
        kind=re.sub(r'[\s_\-－–—()/]','',str(raw or '')).upper()
        if kind in {'연간','연간계약','연간단가','연간단가계약','ANNUALUNITPRICE','ANNUALUNITPRICECONTRACT'}:return True
    return False
