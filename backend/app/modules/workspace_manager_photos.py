"""Verified contact portraits stay behind headquarters authentication."""
import hashlib
import json
import re


def manager_registry(root):
    try:
        data=json.loads((root/'site-manager-photos.json').read_text(encoding='utf-8'))
        return data['photos'] if data.get('schema')==1 and isinstance(data.get('photos'),dict) else {}
    except (OSError,ValueError,TypeError,AttributeError):
        return {}


def verified_manager_photo(site,root,registry):
    code=site['code'];record=registry.get(code)
    if not isinstance(record,dict) or record.get('verified') is not True or record.get('site_code')!=code:return None
    contacts=[c for c in site.get('contacts',[]) if '소장' in str(c.get('role','')).split('·')]
    matched=[c for c in contacts if c.get('contact_id')==record.get('contact_id') and c.get('name')==record.get('name')]
    digest=record.get('sha256','')
    if len(matched)!=1 or record.get('source_kind') not in {'HRD_PROFILE','APPROVED_CONTACT_PHOTO'} or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):return None
    directory=root/'site-manager-photos';file=directory/(digest+'.webp')
    try:
        if directory.is_symlink() or file.is_symlink() or not file.is_file() or not 12<=file.stat().st_size<=128*1024:return None
        raw=file.read_bytes()
        if len(raw)>128*1024 or raw[:4]!=b'RIFF' or raw[8:12]!=b'WEBP' or hashlib.sha256(raw).hexdigest()!=digest:return None
    except OSError:return None
    return {'metadata':{'site_code':code,'contact_id':matched[0]['contact_id'],'name':matched[0]['name'],'url':'/workspace/site-manager-photo/'+code,'content_sha256':digest,'verified':True},'bytes':raw}
