from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..schemas import IPCreate, HostnameUpdate
from ..crud import search, create_ip_with_assignment, update_ip_hostname, ip_history
from ..security import require_user
from ..deps import require_admin, get_current_user, require_write_access
from ..utils import actor_from_user

router = APIRouter(prefix='/api', tags=['ip'])

@router.get('/search')
def api_search(q: str = '', site: str | None = None, vlan_id: int | None = None, status: str | None = None,
               db: Session = Depends(get_session), user=Depends(require_user)):
    rows = search(db, q=q, site_code=site, vlan_id=vlan_id, status=status)
    return [
        {
            'ip_id': ip_obj.id,
            'ip': str(ip_obj.ip),
            'site_id': ip_obj.site_id,
            'site_code': site_obj.code,
            'status': ip_obj.status,
            'vlan_ref': ip_obj.vlan_ref,
            'vlan_name': vlan_obj.name if vlan_obj else None,
            'hostname': assign.hostname if assign else None,
            'label': assign.label if assign else None,
            'notes': assign.notes if assign else None,
            'assignment_updated_at': assign.updated_at.isoformat() if assign else None,
        }
        for ip_obj, assign, site_obj, vlan_obj in rows
    ]

@router.post('/ip')
def api_create_ip(payload: IPCreate, db: Session = Depends(get_session), user=Depends(require_write_access)):
    """Create IP - available to all authenticated users with write access"""
    actor = payload.actor or actor_from_user(user)
    try:
        ip_id = create_ip_with_assignment(
            db,
            ip=payload.ip,
            hostname=payload.hostname,
            actor=actor,
            label=payload.label,
            notes=payload.notes,
            status=payload.status,
            vlan_numeric=payload.vlan_id,
        )
        return {'ip_id': ip_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put('/ip/{ip_id}/hostname')
def api_update_hostname(ip_id: int, payload: HostnameUpdate, db: Session = Depends(get_session), admin=Depends(require_admin)):
    """Update IP - admin only"""
    actor = payload.actor or actor_from_user(admin)
    try:
        assign_id = update_ip_hostname(
            db,
            ip_id=ip_id,
            actor=actor,
            hostname=payload.hostname,
            label=payload.label,
            notes=payload.notes,
            status=payload.status,
            vlan_numeric=payload.vlan_id,
        )
        return {'assignment_id': assign_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get('/ip/{ip_id}/history')
def api_ip_history(ip_id: int, db: Session = Depends(get_session), user=Depends(require_user)):
    try:
        ip_obj, assigns = ip_history(db, ip_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        'ip': str(ip_obj.ip),
        'status': ip_obj.status,
        'vlan_ref': ip_obj.vlan_ref,
        'history': [
            {
                'id': a.id,
                'hostname': a.hostname,
                'label': a.label,
                'notes': a.notes,
                'is_active': a.is_active,
                'updated_by': a.updated_by,
                'updated_at': a.updated_at.isoformat(),
            }
            for a in assigns
        ],
    }

@router.delete('/ip/{ip_id}')
def api_delete_ip(ip_id: int, db: Session = Depends(get_session), admin=Depends(require_admin)):
    """Delete IP address - admin only"""
    from ..models import IPAddress
    from ..crud import audit
    from sqlalchemy import select
    
    ip_obj = db.get(IPAddress, ip_id)
    if not ip_obj:
        raise HTTPException(status_code=404, detail='IP address not found')
    
    # Log deletion for audit
    actor = actor_from_user(admin)
    old_data = {
        'ip': str(ip_obj.ip),
        'status': ip_obj.status,
        'site_id': ip_obj.site_id,
        'vlan_ref': ip_obj.vlan_ref
    }
    audit(db, actor, 'DELETE_IP', 'ip_address', ip_id, old_data, None)
    
    # Delete IP (cascade will delete assignments)
    db.delete(ip_obj)
    db.commit()
    
    return {'ok': True, 'message': 'IP address deleted successfully'}
