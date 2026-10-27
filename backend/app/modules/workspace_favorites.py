"""Small initial examples; explicit per-user stars remain editable."""
import json
from pathlib import Path

def default_favorite_codes(path:Path,name:str,known_codes:set[str])->set[str]:
 try:
  data=json.loads(path.read_text(encoding='utf-8'))
 except FileNotFoundError:
  return set()
 if type(data.get('schema')) is not int or data['schema']!=1 or not isinstance(data.get('by_name'),dict):
  raise ValueError('FAVORITE_DEFAULTS_INVALID')
 values=data['by_name'].get(name,[])
 if not isinstance(values,list) or len(values)>2 or any(not isinstance(code,str) or not code for code in values) or len(set(values))!=len(values):
  raise ValueError('FAVORITE_DEFAULTS_INVALID')
 return set(values)&known_codes
