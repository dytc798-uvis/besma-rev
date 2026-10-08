"""One revisioned configuration for collection, submissions and manual NAS paths."""
import json,re,sqlite3,uuid,unicodedata
from pathlib import Path
from datetime import datetime,timezone
from fastapi import HTTPException
from pydantic import BaseModel,Field,field_validator,model_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError,OperationalError
from app.config.settings import settings
from app.core.datetime_utils import utc_now
from app.modules.document_settings.models import DocumentRequirement,DocumentTypeMaster,SubmissionCycle
from app.modules.sites.models import Site
from app.modules.documents.active_site_scope import in_active_scope,today_kst
from .models import GovernmentCollectionConfiguration,GovernmentCollectionConfigurationHistory

GROUP_IDS=('MONTHLY','WEEKLY','EVENT')
GROUP_LABELS={'MONTHLY':'월간','WEEKLY':'주간','EVENT':'착공시'}
FREQUENCIES={'MONTHLY','WEEKLY','EVENT','ADHOC','HALF_YEARLY'}
def group_for(frequency):return 'EVENT' if frequency in {'EVENT','ADHOC'} else frequency
def display_groups(config):
    groups=list(config['groups']);known={g['id'] for g in groups}
    for item in config['items']:
        group=group_for(item['frequency'])
        if group not in known:
            groups.append({'id':group,'label':{'HALF_YEARLY':'반기'}.get(group,group),'order':90});known.add(group)
    return groups
def segment(value):
    value=unicodedata.normalize('NFC',str(value)).strip()
    if not value or len(value)>100 or re.search(r'[\\/:*?"<>|\x00-\x1f]',value) or value.endswith(('.', ' ')) or value in {'.','..'} or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',value):
        raise ValueError('폴더 이름에 사용할 수 없는 문자가 있습니다.')
    return value

class GroupSetting(BaseModel):
    id:str
    label:str
    order:int=Field(ge=0,le=99)
    @field_validator('id')
    @classmethod
    def valid_id(cls,value):
        if value not in GROUP_IDS:raise ValueError('잘못된 구분입니다.')
        return value
    @field_validator('label')
    @classmethod
    def valid_label(cls,value):return segment(value)

class ItemSetting(BaseModel):
    code:str|None=None
    title:str
    frequency:str
    collection_folder:str
    priority:bool=True
    enabled:bool=True
    required:bool=True
    order:int=Field(default=0,ge=0,le=999)
    @model_validator(mode='after')
    def single_selection(self):
        # Legacy priority remains an API alias, never a second selection switch.
        self.priority=self.enabled
        return self
    @field_validator('title','collection_folder')
    @classmethod
    def valid_name(cls,value):return segment(value)
    @field_validator('frequency')
    @classmethod
    def valid_frequency(cls,value):
        if value not in FREQUENCIES:raise ValueError('잘못된 제출 주기입니다.')
        return value
    @field_validator('code')
    @classmethod
    def valid_code(cls,value):
        if value is not None and not re.fullmatch(r'GOV_[A-Z0-9_]{1,45}',value):raise ValueError('잘못된 서류 식별자입니다.')
        return value

class CollectionSetting(BaseModel):
    revision:int=Field(ge=0)
    groups:list[GroupSetting]=Field(min_length=3,max_length=3)
    items:list[ItemSetting]=Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def unique(self):
        if {g.id for g in self.groups}!=set(GROUP_IDS) or len({g.label.casefold() for g in self.groups})!=3 or len({g.order for g in self.groups})!=3:raise ValueError('구분명과 순서는 서로 달라야 합니다.')
        codes=[i.code for i in self.items if i.code]
        if len(codes)!=len(set(codes)) or len({i.title.casefold() for i in self.items})!=len(self.items):raise ValueError('서류가 중복되었습니다.')
        return self

def read_configuration(main):
    from .core import GOV_CODES,GOV_CATEGORY,CATEGORIES,PRIORITY_CODES,PRIORITY_LABELS
    exists=main.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='government_collection_configurations'").fetchone()
    stored=main.execute('SELECT revision,payload FROM government_collection_configurations WHERE id=1').fetchone() if exists else None
    saved=json.loads(stored['payload']) if stored else {};extra={i['code']:i for i in saved.get('items',[])}
    groups=saved.get('groups') or [{'id':id,'label':GROUP_LABELS[id],'order':n} for n,id in enumerate(GROUP_IDS)]
    placeholders=','.join('?' for _ in GOV_CODES)
    rows=main.execute(f"SELECT r.* FROM document_requirements r JOIN sites s ON s.id=r.site_id WHERE s.site_code IN ({placeholders}) AND r.code LIKE 'GOV_%' ORDER BY r.display_order,r.id",sorted(GOV_CODES)).fetchall()
    items={}
    for row in rows:
        code=row['code']
        if code in items:continue
        metadata=extra.get(code,{})
        title=row['title'].removeprefix('관급 ')
        if not stored:title=PRIORITY_LABELS.get(code,title)
        category=GOV_CATEGORY.get(code)
        items[code]={'code':code,'title':title,'frequency':row['frequency'],'group_id':group_for(row['frequency']),'collection_folder':metadata.get('collection_folder') or (CATEGORIES[category][1] if category else title),'priority':bool(row['is_enabled']),'enabled':bool(row['is_enabled']),'required':bool(row['is_required']),'order':metadata.get('order',row['display_order'])}
    return {'revision':stored['revision'] if stored else 0,'groups':sorted(groups,key=lambda g:g['order']),'items':list(items.values())}

def item_order(item,groups):
    return (next((g['order'] for g in groups if g['id']==group_for(item['frequency'])),99),item.get('order',0),item['code'])

def save_configuration(db,payload,actor_id):
    # Main DB and settings history share one transaction; document IDs and histories are never rewritten.
    from .core import readonly
    with readonly(settings.sqlite_path) as main:before=read_configuration(main)
    if payload.revision!=before['revision']:raise HTTPException(409,'다른 사용자가 설정을 변경했습니다. 새로고침 후 저장하세요.')
    old_codes={i['code'] for i in before['items']};new_codes={i.code for i in payload.items if i.code}
    if not old_codes<=new_codes:raise HTTPException(422,'기존 서류는 삭제 대신 제외를 선택하세요.')
    if new_codes-old_codes:raise HTTPException(422,'기존 서류 식별자를 변경할 수 없습니다.')
    root=Path(settings.storage_root)/'collection-monitor/settings-backups';root.mkdir(parents=True,exist_ok=True,mode=0o750)
    backup=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex+'.sqlite3')
    with sqlite3.connect(Path(settings.sqlite_path).resolve().as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(backup) as dest:source.backup(dest)
    backup.chmod(0o640)
    try:
        stored=db.get(GovernmentCollectionConfiguration,1)
        revision=before['revision']+1
        if stored:
            result=db.execute(update(GovernmentCollectionConfiguration).where(GovernmentCollectionConfiguration.id==1,GovernmentCollectionConfiguration.revision==payload.revision).values(revision=revision,updated_by=actor_id,updated_at=utc_now()))
            if result.rowcount!=1:raise HTTPException(409,'설정이 변경되었습니다. 새로고침하세요.')
        else:
            db.add(GovernmentCollectionConfiguration(id=1,revision=revision,payload='{}',updated_by=actor_id));db.flush()
        active=[s for s in db.query(Site).all() if in_active_scope(s,today_kst(),'government')]
        if not active:raise HTTPException(409,'활성 관급 현장이 없습니다.')
        items=[]
        for entry in payload.items:
            data=entry.model_dump();code=entry.code or 'GOV_CUSTOM_'+uuid.uuid4().hex[:20].upper();data['code']=code;data['group_id']=group_for(entry.frequency)
            master=db.query(DocumentTypeMaster).filter(DocumentTypeMaster.code==code).first()
            cycle=db.query(SubmissionCycle).filter(SubmissionCycle.code==entry.frequency).first()
            if cycle is None:
                cycle=SubmissionCycle(code=entry.frequency,name=GROUP_LABELS.get(entry.frequency,entry.frequency),sort_order=90,is_active=True,is_auto_generatable=False);db.add(cycle);db.flush()
            if master is None:
                master=DocumentTypeMaster(code=code,name=entry.title,default_cycle_id=cycle.id,is_active=True,is_required_default=entry.required);db.add(master);db.flush()
            else:master.name=entry.title
            for site in active:
                requirements=db.query(DocumentRequirement).filter(DocumentRequirement.site_id==site.id,DocumentRequirement.code==code).all()
                if not requirements:
                    requirement=DocumentRequirement(site_id=site.id,document_type_id=master.id,code=code,title=entry.title,frequency=entry.frequency,is_enabled=entry.enabled,is_required=entry.required,display_order=entry.order,override_cycle_id=cycle.id);db.add(requirement)
                for requirement in requirements:
                    requirement.title=entry.title;requirement.frequency=entry.frequency;requirement.is_enabled=entry.enabled;requirement.is_required=entry.required;requirement.display_order=entry.order;requirement.override_cycle_id=cycle.id
            items.append(data)
        content={'groups':[g.model_dump() for g in payload.groups],'items':items}
        encoded=json.dumps(content,ensure_ascii=False)
        db.flush();db.execute(update(GovernmentCollectionConfiguration).where(GovernmentCollectionConfiguration.id==1).values(payload=encoded))
        db.add(GovernmentCollectionConfigurationHistory(revision=revision,payload=encoded,actor_id=actor_id,backup_name=backup.name));db.commit()
    except (IntegrityError,OperationalError):
        db.rollback();raise HTTPException(409,'다른 설정 저장과 겹쳤습니다. 새로고침 후 다시 저장하세요.')
    except Exception:db.rollback();raise
    with readonly(settings.sqlite_path) as main:return read_configuration(main)
