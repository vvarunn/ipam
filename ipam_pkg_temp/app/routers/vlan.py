from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_session
from ..models import VLAN, Site
from ..schemas import VlanCreate, VlanUpdate
from ..security import require_user
from ..deps import require_admin
from ..utils import actor_from_user
from ..crud import audit

router = APIRouter(prefix='/api/vlan', tags=['vlan'])

@router.get('/')
def list_vlans(site: str | None = None, db: Session = Depends(get_session), user=Depends(require_user)):
    from ipaddress import ip_network
    from ..models import IPAddress
    from sqlalchemy import func
    
    stmt = select(VLAN)
    if site:
        site_obj = db.scalar(select(Site).where(Site.code == site))
        if not site_obj:
            raise HTTPException(400, 'Invalid site')
        stmt = stmt.where(VLAN.site_id == site_obj.id)

    vlans = db.execute(stmt.order_by(VLAN.site_id, VLAN.vlan_id)).scalars().all()
    
    result = []
    for v in vlans:
        # Calculate total IPs in the CIDR
        network = ip_network(v.cidr, strict=False)
        total_ips = network.num_addresses
        # Subtract network and broadcast addresses for usable count
        usable_ips = total_ips - 2 if total_ips > 2 else total_ips
        
        # Count allocated IPs in this VLAN
        allocated_count = db.scalar(
            select(func.count(IPAddress.id)).where(IPAddress.vlan_ref == v.id)
        ) or 0
        
        # Calculate free IPs
        free_ips = usable_ips - allocated_count
        
        result.append({
            'id': v.id,
            'site_id': v.site_id,
            'vlan_id': v.vlan_id,
            'name': v.name,
            'cidr': str(v.cidr),
            'gateway': str(v.gateway) if v.gateway else None,
            'description': v.description,
            'free_ips': free_ips,
            'total_ips': usable_ips,
            'allocated_ips': allocated_count
        })
    
    return result

@router.post('/')
def create_vlan(payload: VlanCreate, db: Session = Depends(get_session), user=Depends(require_admin)):
    site_obj = db.scalar(select(Site).where(Site.code == payload.site_code))
    if not site_obj:
        raise HTTPException(400, 'Invalid site_code')

    exists = db.scalar(select(VLAN).where(VLAN.site_id == site_obj.id, VLAN.vlan_id == payload.vlan_id))
    if exists:
        raise HTTPException(400, 'VLAN already exists')

    vlan = VLAN(
        site_id=site_obj.id,
        vlan_id=payload.vlan_id,
        name=payload.name,
        cidr=payload.cidr,
        gateway=payload.gateway,
        description=payload.description,
    )
    db.add(vlan)
    db.flush()

    audit(db, actor_from_user(user), 'CREATE_VLAN', 'vlan', vlan.id, None, payload.model_dump())
    db.commit()
    return {'id': vlan.id}

@router.get('/{vlan_db_id}/free-ips')
def get_free_ips(vlan_db_id: int, db: Session = Depends(get_session), user=Depends(require_user)):
    from ipaddress import ip_network, ip_address
    from ..models import IPAddress
    
    vlan = db.get(VLAN, vlan_db_id)
    if not vlan:
        raise HTTPException(404, 'VLAN not found')
    
    # Get all IPs in the CIDR range
    network = ip_network(vlan.cidr, strict=False)
    all_ips = list(network.hosts())  # Excludes network and broadcast
    
    # Get allocated IPs for this VLAN
    allocated_ips = db.execute(
        select(IPAddress.ip).where(IPAddress.vlan_ref == vlan.id)
    ).scalars().all()
    allocated_set = {ip_address(str(ip)) for ip in allocated_ips}
    
    # Calculate free IPs
    free_ips = [str(ip) for ip in all_ips if ip not in allocated_set]
    
    return {
        'vlan_id': vlan.vlan_id,
        'cidr': str(vlan.cidr),
        'total': len(all_ips),
        'allocated': len(allocated_set),
        'free': len(free_ips),
        'free_ips': free_ips[:500]  # Limit to first 500 for performance
    }

@router.put('/{vlan_db_id}')
def update_vlan(vlan_db_id: int, payload: VlanUpdate, db: Session = Depends(get_session), user=Depends(require_admin)):
    vlan = db.get(VLAN, vlan_db_id)
    if not vlan:
        raise HTTPException(404, 'VLAN not found')

    old = {'name': vlan.name, 'cidr': str(vlan.cidr), 'gateway': str(vlan.gateway) if vlan.gateway else None, 'description': vlan.description}
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(vlan, k, v)

    audit(db, actor_from_user(user), 'UPDATE_VLAN', 'vlan', vlan.id, old, payload.model_dump(exclude_unset=True))
    db.commit()
    return {'ok': True}

@router.delete('/{vlan_db_id}')
def delete_vlan(vlan_db_id: int, db: Session = Depends(get_session), user=Depends(require_admin)):
    vlan = db.get(VLAN, vlan_db_id)
    if not vlan:
        raise HTTPException(404, 'VLAN not found')

    old = {'site_id': vlan.site_id, 'vlan_id': vlan.vlan_id, 'cidr': str(vlan.cidr)}
    db.delete(vlan)
    audit(db, actor_from_user(user), 'DELETE_VLAN', 'vlan', vlan_db_id, old, None)
    db.commit()
    return {'ok': True}
