"""Candidate module + read-only operating DB; report aggregate readiness only."""
import importlib.util,json,sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
sys.path.insert(0,'/srv/besma/backend');root=Path(sys.argv[1])
spec=importlib.util.spec_from_file_location('candidate_home',root/'backend/app/modules/workspace_home.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=root/'private'
engine=create_engine('sqlite:///file:/srv/besma/database/besma.db?mode=ro&uri=true')
with Session(engine) as db:
    readiness=m.readiness(db);home=m.home(db)
print(json.dumps({'readiness':readiness,'site_catalog':home['sites'],'active_sites':len(home['sites']),'located_sites':sum(s['latitude'] is not None for s in home['sites']),'regions':home['regions'],'today_attendance':home['attendance']},ensure_ascii=True))
