from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import PublicIPCreate, PublicIPUpdate
from ..crud import search_public_ips, create_public_ip, update_public_ip, delete_public_ip
from ..security import require_user
from ..deps import require_admin, get_current_user, require_write_access
from ..utils import actor_from_user, is_admin

router = APIRouter(tags=['public_ip'])
templates = Jinja2Templates(directory='app/templates')

@router.get('/public-ips', response_class=HTMLResponse)
def public_ips_page(request: Request, q: str = '', status: str | None = None, db: Session = Depends(get_session)):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/')
    rows = search_public_ips(db, q=q, status=status)
    return templates.TemplateResponse('public_ips.html', {
        'request': request, 
        'rows': rows, 
        'q': q, 
        'status': status, 
        'user': user, 
        'is_admin': is_admin(user)
    })

@router.get('/api/public-ip')
def api_search_public_ips(q: str = '', status: str | None = None,
               db: Session = Depends(get_session), user=Depends(require_user)):
    rows = search_public_ips(db, q=q, status=status)
    return [
        {
            'id': p.id,
            'public_ip': str(p.public_ip),
            'private_ip': str(p.private_ip) if p.private_ip else None,
            'fqdn': p.fqdn,
            'owner': p.owner,
            'status': p.status,
            'notes': p.notes,
            'updated_at': p.updated_at.isoformat(),
        }
        for p in rows
    ]

@router.post('/api/public-ip')
def api_create_public_ip(payload: PublicIPCreate, db: Session = Depends(get_session), user=Depends(require_write_access)):
    actor = payload.actor or actor_from_user(user)
    try:
        ip_id = create_public_ip(
            db,
            actor=actor,
            public_ip=payload.public_ip,
            private_ip=payload.private_ip,
            fqdn=payload.fqdn,
            owner=payload.owner,
            status=payload.status,
            notes=payload.notes
        )
        return {'id': ip_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put('/api/public-ip/{ip_id}')
def api_update_public_ip(ip_id: int, payload: PublicIPUpdate, db: Session = Depends(get_session), admin=Depends(require_admin)):
    actor = payload.actor or actor_from_user(admin)
    try:
        ip_id = update_public_ip(
            db,
            actor=actor,
            public_ip_id=ip_id,
            private_ip=payload.private_ip,
            fqdn=payload.fqdn,
            owner=payload.owner,
            status=payload.status,
            notes=payload.notes
        )
        return {'id': ip_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete('/api/public-ip/{ip_id}')
def api_delete_public_ip(ip_id: int, db: Session = Depends(get_session), admin=Depends(require_admin)):
    actor = actor_from_user(admin)
    try:
        delete_public_ip(db, actor=actor, public_ip_id=ip_id)
        return {'ok': True, 'message': 'Public IP removed successfully'}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
