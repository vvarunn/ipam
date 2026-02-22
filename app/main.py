import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from .db import engine, get_session, SessionLocal
from .models import Base
from .crud import ensure_sites, ensure_indexes, search, fix_ip_sites_and_vlans
from .auth_sso import router as auth_router, setup_oauth
from .utils import is_admin
from .user_crud import ensure_admin_user

from .routers.ip import router as ip_router
from .routers.vlan import router as vlan_router
from .routers.bulk import router as bulk_router
from .routers.export import router as export_router
from .routers.dashboard import router as dashboard_router
from .routers.users import router as users_router
from .routers.settings import router as settings_router
from .routers.audit import router as audit_router

APP_TITLE = os.getenv('APP_TITLE', 'IPAM')
__version__ = "1.1.0"

app = FastAPI(title=APP_TITLE, version=__version__)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv('SESSION_SECRET', 'dev_secret'),
    https_only=False,
    same_site='lax'
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory='app/templates')

# Inject version into all templates globally
@app.middleware("http")
async def add_template_context(request: Request, call_next):
    # This ensures version is available in templates if we set it in request state
    request.state.app_version = __version__
    response = await call_next(request)
    return response

# Also directly patch Jinja2 environment as a cleaner global
templates.env.globals['app_version'] = __version__

@app.on_event('startup')
def startup():
    setup_oauth()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_sites(db)
        ensure_indexes(db)
        fix_ip_sites_and_vlans(db)
        
        # Create default admin user if configured
        admin_username = os.getenv('LOCAL_ADMIN_USERNAME')
        admin_password = os.getenv('LOCAL_ADMIN_PASSWORD')
        if admin_username and admin_password:
            admin_email = os.getenv('LOCAL_ADMIN_EMAIL')
            try:
                print(f"DEBUG: Ensuring admin user '{admin_username}', password length: {len(admin_password)}")
                ensure_admin_user(db, admin_username, admin_password, admin_email)
            except Exception as e:
                print(f"ERROR: Failed to ensure admin user: {e}")
    finally:
        db.close()

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request):
    user = request.session.get('user')
    if not user:
        return templates.TemplateResponse('login.html', {'request': request})
    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'user': user,
        'is_admin': is_admin(user)
    })

@app.get('/search', response_class=HTMLResponse)
def search_page(request: Request, q: str = '', site: str | None = None, vlan_id: int | None = None, status: str | None = None, db: Session = Depends(get_session)):
    user = request.session.get('user')
    if not user:
        return templates.TemplateResponse('login.html', {'request': request})
    rows = search(db, q=q, site_code=site, vlan_id=vlan_id, status=status)
    return templates.TemplateResponse('index.html', {'request': request, 'rows': rows, 'q': q, 'site': site, 'vlan_id': vlan_id, 'status': status, 'user': user, 'is_admin': is_admin(user)})

@app.get('/bulk', response_class=HTMLResponse)
def bulk_page(request: Request):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/')
    return templates.TemplateResponse('bulk.html', {'request': request, 'user': user, 'is_admin': is_admin(user)})

@app.get('/export', response_class=HTMLResponse)
def export_page(request: Request):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/')
    return templates.TemplateResponse('export.html', {'request': request, 'user': user, 'is_admin': is_admin(user)})

@app.get('/vlans', response_class=HTMLResponse)
def vlan_page(request: Request):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/')
    return templates.TemplateResponse('vlans.html', {'request': request, 'user': user, 'is_admin': is_admin(user)})

@app.get('/settings', response_class=HTMLResponse)
def settings_page(request: Request):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/')
    
    if not is_admin(user):
        return RedirectResponse(url='/')
        
    return templates.TemplateResponse('settings.html', {'request': request, 'user': user, 'is_admin': True})

# routers
app.include_router(auth_router)
app.include_router(ip_router)
app.include_router(vlan_router)
app.include_router(bulk_router)
app.include_router(export_router)
app.include_router(dashboard_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(audit_router)
