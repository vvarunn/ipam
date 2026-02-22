import os
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
import json
from urllib.parse import urlparse
from onelogin.saml2.auth import OneLogin_Saml2_Auth

from .db import get_session, SessionLocal
from .models import User, Settings
from .password import verify_password

router = APIRouter(prefix='/auth', tags=['auth'])
oauth = OAuth()

def get_sso_config(db: Session = None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
        
    try:
        setting = db.scalar(select(Settings).where(Settings.key == 'sso_config'))
        if setting and setting.value:
            config = json.loads(setting.value)
            return config
            
        # Fallback to old oidc_config
        setting = db.scalar(select(Settings).where(Settings.key == 'oidc_config'))
        if setting and setting.value:
            config = json.loads(setting.value)
            if config.get('enabled'):
                config['sso_type'] = 'oidc'
            return config
    except Exception as e:
        print(f"Error loading SSO config: {e}")
    finally:
        if close_db:
            db.close()
            
    return None

def setup_oauth(config: dict = None):
    if config is None:
        config = get_sso_config()
        
    if not config or config.get('sso_type') != 'oidc' or not config.get('discovery_url'):
        return
        
    # Unregister first just in case we are updating the config
    if 'sso_client' in oauth._registry:
        del oauth._registry['sso_client']
        
    oauth.register(
        name='sso_client',
        server_metadata_url=config.get('discovery_url'),
        client_id=config.get('client_id'),
        client_secret=config.get('client_secret'),
        client_kwargs={'scope': config.get('scopes', 'openid profile email')},
    )

def prepare_fastapi_request(request: Request):
    url_data = urlparse(str(request.url))
    return {
        'https': 'on' if request.url.scheme == 'https' or request.headers.get("x-forwarded-proto") == 'https' else 'off',
        'http_host': request.headers.get('host', url_data.netloc),
        'server_port': url_data.port,
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
        'post_data': {}
    }

def get_saml_settings(config: dict, request: Request):
    scheme = 'https' if request.url.scheme == 'https' or request.headers.get("x-forwarded-proto") == 'https' else 'http'
    base_url = f"{scheme}://{request.headers.get('host', request.url.netloc)}"

    return {
        "strict": False,
        "debug": True,
        "sp": {
            "entityId": f"{base_url}/auth/saml/metadata",
            "assertionConsumerService": {
                "url": f"{base_url}/auth/saml/acs",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
        },
        "idp": {
            "entityId": config.get("saml_idp_entity_id"),
            "singleSignOnService": {
                "url": config.get("saml_idp_sso_url"),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "x509cert": config.get("saml_idp_x509_cert", "")
        }
    }

@router.get('/login')
async def login(request: Request, db: Session = Depends(get_session)):
    config = get_sso_config(db)
    
    if not config or config.get('sso_type') in ['none', None]:
        raise HTTPException(status_code=400, detail='SSO is not enabled')
        
    if config.get('sso_type') == 'saml':
        req = prepare_fastapi_request(request)
        auth = OneLogin_Saml2_Auth(req, get_saml_settings(config, request))
        return RedirectResponse(url=auth.login())
        
    elif config.get('sso_type') == 'oidc':
        redirect_uri = config.get('redirect_uri')
        if not redirect_uri:
            scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
            redirect_uri = f"{scheme}://{request.url.netloc}/auth/callback"
            
        setup_oauth(config)
        
        if 'sso_client' not in oauth._registry:
            raise HTTPException(status_code=500, detail='OIDC configuration error: Client not registered. Please check Discovery URL.')
            
        try:
            return await oauth.sso_client.authorize_redirect(request, redirect_uri)
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f'Failed to communicate with OIDC provider. Please check the Discovery URL and network connectivity. Error: {str(e)}'
            )

@router.get('/callback')
async def callback(request: Request, db: Session = Depends(get_session)):
    config = get_sso_config(db)
    setup_oauth(config)

    if 'sso_client' not in oauth._registry:
        raise HTTPException(status_code=500, detail='OIDC configuration error: Client not registered during callback')

    try:
        token = await oauth.sso_client.authorize_access_token(request)
        userinfo = token.get('userinfo') or await oauth.sso_client.userinfo(token=token)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f'Failed to process OIDC callback. Ensure proper OIDC configuration. Error: {str(e)}'
        )

    request.session['user'] = {
        'sub': userinfo.get('sub'),
        'email': userinfo.get('email'),
        'name': userinfo.get('name') or userinfo.get('preferred_username'),
        'groups': userinfo.get('groups', []),
    }
    return RedirectResponse(url='/')

@router.post('/saml/acs')
async def saml_acs(request: Request, db: Session = Depends(get_session)):
    config = get_sso_config(db)
    if not config or config.get('sso_type') != 'saml':
        raise HTTPException(status_code=400, detail='SAML is not enabled')

    form_data = await request.form()
    req = prepare_fastapi_request(request)
    req['post_data'] = dict(form_data)
    
    auth = OneLogin_Saml2_Auth(req, get_saml_settings(config, request))
    auth.process_response()
    
    errors = auth.get_errors()
    if errors:
        raise HTTPException(status_code=401, detail=f"SAML processing error: {', '.join(errors)}")

    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="SAML Authentication Failed")

    attributes = auth.get_attributes()
    
    email = attributes.get('email', [''])[0] or attributes.get('urn:oid:0.9.2342.19200300.100.1.3', [''])[0] or auth.get_nameid()
    name = attributes.get('name', [''])[0] or attributes.get('urn:oid:2.16.840.1.113730.3.1.241', [''])[0] or email
    groups = attributes.get('groups', []) or attributes.get('http://schemas.xmlsoap.org/claims/Group', [])
    
    request.session['user'] = {
        'sub': auth.get_nameid(),
        'email': email,
        'name': name,
        'groups': groups,
    }
    
    return RedirectResponse(url='/', status_code=303)
    
@router.get('/saml/metadata')
async def saml_metadata(request: Request, db: Session = Depends(get_session)):
    config = get_sso_config(db)
    if not config or config.get('sso_type') != 'saml':
        raise HTTPException(status_code=400, detail='SAML is not enabled')

    saml_settings = get_saml_settings(config, request)
    from onelogin.saml2.settings import OneLogin_Saml2_Settings
    settings = OneLogin_Saml2_Settings(saml_settings)
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)
    
    if len(errors) == 0:
        from fastapi.responses import Response
        return Response(content=metadata, media_type="application/xml")
    else:
        raise HTTPException(status_code=500, detail=f"Invalid SP metadata: {', '.join(errors)}")

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
