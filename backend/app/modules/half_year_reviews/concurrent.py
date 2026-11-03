"""Apply only edited fields to the latest review; retain concurrent photo additions."""
from copy import deepcopy
_MISSING=object()

def merge_edits(base,local,current):
    if local==base:return deepcopy(current)
    if isinstance(local,dict)and isinstance(base,dict)and isinstance(current,dict):
        result=deepcopy(current)
        for key in set(base)|set(local):
            before=base.get(key,_MISSING);after=local.get(key,_MISSING)
            if before==after:continue
            if after is _MISSING:result.pop(key,None)
            elif before is _MISSING:result[key]=deepcopy(after)
            else:result[key]=merge_edits(before,after,current.get(key))
        return result
    if all(isinstance(x,list)for x in [base,local,current]):
        if all(isinstance(x,(str,int))for values in [base,local,current]for x in values):
            return [x for x in current if x not in base or x in local]+[x for x in local if x not in current]
        if all(isinstance(x,dict)and 'id'in x for values in [base,local,current]for x in values):
            a={x['id']:x for x in base};b={x['id']:x for x in local};c={x['id']:x for x in current}
            merged=merge_edits(a,b,c);return list(merged.values())
    return deepcopy(local)

def confirm_evidence(data,eid,name,stamp):
    previous=data['evidence'].get(eid,{})
    data['evidence'][eid]={**previous,'checked':True,'hold':bool(previous.get('hold')),'by':name,'at':stamp}
