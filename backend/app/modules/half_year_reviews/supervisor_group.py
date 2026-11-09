"""One anonymous supervisor assessment per site; retain raw historical rosters."""
from copy import deepcopy

def members(data):return deepcopy(data.get('supervisor_members',data.get('subjects',{}).get('supervisor',[])))

def subject(data):
    people=members(data)
    if not people:
        records=data.get('assessments',{});anchor=data.get('supervisor_group_id')or next((k.split(':',1)[1]for k,v in records.items()if k.startswith('supervisor:')and v.get('completed')),None)or next((k.split(':',1)[1]for k in records if k.startswith('supervisor:')),None)or'00000000000000000000000000000001'
        return {'id':anchor,'name':''}
    records=data.get('assessments',{});anchor=data.get('supervisor_group_id')
    if not anchor:
        anchor=next((p['id']for p in people if records.get('supervisor:'+p['id'],{}).get('completed')),None)
    if not anchor:
        anchor=next((p['id']for p in people if records.get('supervisor:'+p['id'],{}).get('draft',{}).get('result',{}).get('graded',0)),people[0]['id'])
    return {'id':anchor,'name':''}

def project_data(data):
    value=deepcopy(data);people=members(data);group=subject(data);value.pop('supervisor_members',None);value.setdefault('subjects',{})['supervisor']=[group]
    for key,record in value.get('assessments',{}).items():
        if not key.startswith('supervisor:'):continue
        for kind in ['draft','completed']:
            if record.get(kind):record[kind]['subject_name']=''
    return value

def project(response):
    value=deepcopy(response)
    if isinstance(value.get('data'),dict):value['data']=project_data(value['data'])
    return value
