"""Read-only shared pages for authenticated HQ safety users."""
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.config.settings import settings
from app.core.auth import get_current_user

router = APIRouter(prefix='/page-share', tags=['page-share'])
CONTACTS = Path(settings.storage_root) / 'hq-page-share' / 'site-manager-contacts.json'

def authorized(user=Depends(get_current_user)):
    if getattr(user.role, 'value', user.role) != 'HQ_SAFE' or not user.is_active:
        raise HTTPException(403, '안전보건실에서 이용할 수 있습니다.')
    return user

def private_response(data):
    return JSONResponse(data, headers={'Cache-Control':'private, no-store','Vary':'Authorization'})

@router.get('/capabilities')
def capabilities(user=Depends(authorized)):
    return private_response({'can_read':True,'version':'2026.10.20.1'})

@router.get('/site-manager-contacts')
def contacts(user=Depends(authorized)):
    if not CONTACTS.is_file():
        raise HTTPException(503, '연락처를 준비하고 있습니다.')
    data=json.loads(CONTACTS.read_text(encoding='utf-8'))
    return private_response(data)
