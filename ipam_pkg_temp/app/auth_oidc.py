import os
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
import json

from .db import get_session, SessionLocal
from .models import User, Settings
from .password import verify_password

router = APIRouter(prefix='/auth', tags=['auth'])
oauth = OAuth()

def get_oidc_config(db: Session = None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
        
    try:
        setting = db.scalar(select(Settings).where(Settings.key == 'oidc_config'))
        if setting and setting.value:
            config = json.loads(setting.value)
            return config
    except Exception:
        pass
    finally:
        if close_db:
            db.close()
            
    return None

def setup_oauth():
    config = get_oidc_config()
    if not config or not config.get('enabled') or not config.get('discovery_url'):
        return
        
    oauth.register(
        name='omnissa',
        server_metadata_url=config.get('discovery_url'),
        client_id=config.get('client_id'),
        client_secret=config.get('client_secret'),
        client_kwargs={'scope': config.get('scopes', 'openid profile email')},
    )

@router.get('/login')
async def login(request: Request, db: Session = Depends(get_session)):
    config = get_oidc_config(db)
    
    if not config or not config.get('enabled'):
        raise HTTPException(status_code=400, detail='OIDC is not enabled')
        
    redirect_uri = config.get('redirect_uri')
    if not redirect_uri:
        # Fallback to current URL if not explicitly configured
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        redirect_uri = f"{scheme}://{request.url.netloc}/auth/callback"
        
    setup_oauth() # Ensure OAuth is set up with latest config
    
    if 'omnissa' not in oauth._registry:
        raise HTTPException(status_code=500, detail='OIDC configuration error')
        
    return await oauth.omnissa.authorize_redirect(request, redirect_uri)

@router.get('/callback')
async def callback(request: Request):
    token = await oauth.omnissa.authorize_access_token(request)
    userinfo = token.get('userinfo') or await oauth.omnissa.userinfo(token=token)

    request.session['user'] = {
        'sub': userinfo.get('sub'),
        'email': userinfo.get('email'),
        'name': userinfo.get('name') or userinfo.get('preferred_username'),
        'groups': userinfo.get('groups', []),
    }
    return RedirectResponse(url='/')

@router.get('/logout')
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/')

class LocalLoginRequest(BaseModel):
    username: str
    password: str

@router.post('/local/login')
def local_login(login_data: LocalLoginRequest, request: Request, db: Session = Depends(get_session)):
    # Find user by username
    user = db.scalar(select(User).where(User.username == login_data.username))
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail='Invalid credentials')
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    
    # Set session with user data
    request.session['user'] = {
        'sub': str(user.id),
        'email': user.email,
        'name': user.full_name or user.username,
        'username': user.username,
        'groups': user.groups or ([os.getenv('ADMIN_GROUP', 'IPAM-Admins')] if user.is_admin else []),
        'is_local': True
    }
    
    return {'ok': True, 'message': 'Login successful'}
