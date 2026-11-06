"""One supervisor assessment per site, with the complete designated-name roster."""
from copy import deepcopy

def members(data):return deepcopy(data.get('supervisor_members',data.get('subjects',{}).get('supervisor',[])))

def subject(data):
    people=members(data)
    if not people:return None
    records=data.get('assessments',{});anchor=data.get('supervisor_group_id')
    if not anchor:
        anchor=next((p['id']for p in people if records.get('supervisor:'+p['id'],{}).get('completed')),None)
    if not anchor:
        anchor=next((p['id']for p in people if records.get('supervisor:'+p['id'],{}).get('draft',{}).get('result',{}).get('graded',0)),people[0]['id'])
    return {'id':anchor,'name':' / '.join(dict.fromkeys(p['name']for p in people))}

def project_data(data):
    value=deepcopy(data);people=members(data);group=subject(data);value['supervisor_members']=people;value.setdefault('subjects',{})['supervisor']=[group]if group else[]
    if group:
        record=value.get('assessments',{}).get('supervisor:'+group['id'],{})
        for kind in ['draft','completed']:
            if record.get(kind):record[kind]['subject_name']=group['name']
    return value

def project(response):
    value=deepcopy(response)
    if isinstance(value.get('data'),dict):value['data']=project_data(value['data'])
    return value
