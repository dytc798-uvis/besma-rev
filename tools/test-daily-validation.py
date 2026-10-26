"""Validate actual allowed ERP projection and reject corrupt metadata; no record output."""
import importlib.util,json,sys
from pathlib import Path
from copy import deepcopy
root=Path(sys.argv[1]);tools=root/'release/tools'
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),tools/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
build=load('build-daily-attendance');receive=load('receive-workspace-attendance')
receipt=json.loads(Path('D:/JSI/safety-workbench/work/attendance-daily/2026-10-26/latest.json').read_text(encoding='utf-8-sig'))
catalog=json.loads((root/'private/dashboard-catalog.json').read_text(encoding='utf-8'))
sources=[p for p in (Path.home()/'Downloads').glob('출역일보*.xls') if build.sha(p)==receipt['SourceSha256']];assert len(sources)==1
data=build.build(sources[0],receipt,catalog);assert data['people']==727 and len(data['sites'])==52 and all(s['code'] for s in data['sites'])
assert all(set(person)=={'rrn_hash','site_code'} for person in data['identities']);assert all(set(site)=={'name','code','people'} for site in data['sites']);receive.validate(data)
for field,value in [('SourceSha256','0'*64),('People',728),('Date','2026-10-25')]:
    corrupt={**receipt,field:value}
    try:build.build(sources[0],corrupt,catalog);raise AssertionError('Corrupt receipt accepted')
    except ValueError:pass
for mutate in [lambda d:d.update(people=728),lambda d:d['identities'][0].update(phone='excluded'),lambda d:d['sites'][0].update(person_name='excluded')]:
    corrupt=deepcopy(data);mutate(corrupt)
    try:receive.validate(corrupt);raise AssertionError('Corrupt daily payload accepted')
    except ValueError:pass
print(json.dumps({'passed':True,'people':727,'sites':52,'checks':['exact source/date/count','canonical ERP alias mapping','no name/phone/raw identity fields','corrupt metadata and extra sensitive fields rejected']}))
