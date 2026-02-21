from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import json

from app.db import get_session
from app.models import Settings
from app.deps import require_admin
from app.crud import audit

router = APIRouter(prefix='/api/settings', tags=['settings'])

class OIDCSettings(BaseModel):
    enabled: bool = False
    discovery_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    scopes: str = 'openid profile email'

class AppSettings(BaseModel):
    app_url: Optional[str] = None
    ssl_cert: Optional[str] = None

def get_setting(db: Session, key: str) -> Optional[str]:
    """Get a setting value from database"""
    setting = db.scalar(select(Settings).where(Settings.key == key))
    return setting.value if setting else None

def set_setting(db: Session, key: str, value: str, encrypted: bool = False, actor: str = 'admin'):
    """Set a setting value in database"""
    setting = db.scalar(select(Settings).where(Settings.key == key))
    old_value = setting.value if setting else None
    
    if setting:
        setting.value = value
        setting.encrypted = encrypted
        setting.updated_by = actor
    else:
        setting = Settings(key=key, value=value, encrypted=encrypted, updated_by=actor)
        db.add(setting)
    
    audit(db, actor, 'UPDATE_SETTING', 'settings', None, {'key': key, 'value': old_value}, {'key': key})
    return setting

@router.get('/oidc', response_model=OIDCSettings)
def get_oidc_settings(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Get OIDC configuration (admin only)"""
    settings_json = get_setting(db, 'oidc_config')
    
    if settings_json:
        try:
            return OIDCSettings(**json.loads(settings_json))
        except:
            pass
    
    return OIDCSettings()

@router.put('/oidc')
def update_oidc_settings(
    settings: OIDCSettings,
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Update OIDC configuration (admin only)"""
    settings_dict = settings.model_dump()
    settings_json = json.dumps(settings_dict)
    
    set_setting(db, 'oidc_config', settings_json, encrypted=False, actor=admin.get('username', 'admin'))
    db.commit()
    
    return {'ok': True, 'message': 'OIDC settings updated successfully'}

@router.get('/application', response_model=AppSettings)
def get_app_settings(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Get Application Configuration (admin only)"""
    settings_json = get_setting(db, 'app_config')
    
    if settings_json:
        try:
            return AppSettings(**json.loads(settings_json))
        except:
            pass
    
    return AppSettings()

@router.put('/application')
def update_app_settings(
    settings: AppSettings,
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Update Application Configuration (admin only)"""
    settings_dict = settings.model_dump()
    settings_json = json.dumps(settings_dict)
    
    set_setting(db, 'app_config', settings_json, encrypted=False, actor=admin.get('username', 'admin'))
    db.commit()
    
    return {'ok': True, 'message': 'Application settings updated successfully'}

@router.get('/siem')
def get_siem_settings(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Get SIEM export settings (admin only)"""
    settings_json = get_setting(db, 'siem_config')
    
    if settings_json:
        try:
            return json.loads(settings_json)
        except:
            pass
    
    return {
        'enabled': False,
        'endpoint': '',
        'format': 'json'
    }

@router.put('/siem')
def update_siem_settings(
    settings: dict,
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Update SIEM export settings (admin only)"""
    settings_json = json.dumps(settings)
    
    set_setting(db, 'siem_config', settings_json, encrypted=False, actor=admin.get('username', 'admin'))
    db.commit()
    
    return {'ok': True, 'message': 'SIEM settings updated successfully'}
