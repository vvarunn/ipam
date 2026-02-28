import io
import pandas as pd
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_session
from ..security import require_user
from ..utils import actor_from_user
from ..crud import search, audit

router = APIRouter(prefix='/api/export', tags=['export'])

@router.get('/')
def export(q: str = '', site: str | None = None, vlan_id: int | None = None, status: str | None = None, fmt: str = 'csv',
           db: Session = Depends(get_session), user=Depends(require_user)):
    rows = search(db, q=q, site_code=site, vlan_id=vlan_id, status=status)

    data = []
    for ip_obj, assign in rows:
        data.append({
            'ip': str(ip_obj.ip),
            'status': ip_obj.status,
            'vlan_ref': ip_obj.vlan_ref,
            'hostname': assign.hostname if assign else None,
            'label': assign.label if assign else None,
            'notes': assign.notes if assign else None,
            'assignment_updated_at': assign.updated_at.isoformat() if assign else None,
        })

    df = pd.DataFrame(data)
    actor = actor_from_user(user)
    audit(db, actor, 'EXPORT', 'ip_address', None, None, {'fmt': fmt, 'site': site, 'q': q, 'vlan_id': vlan_id, 'status': status, 'rows': len(df)})
    db.commit()

    if fmt.lower() == 'xlsx':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='export')
        output.seek(0)
        return StreamingResponse(output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=ip_export.xlsx'})

    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type='text/csv',
                             headers={'Content-Disposition': 'attachment; filename=ip_export.csv'})

@router.get('/vlan')
def export_vlan(site: str | None = None, fmt: str = 'csv',
                db: Session = Depends(get_session), user=Depends(require_user)):
    from ipaddress import ip_network
    from ..models import IPAddress, VLAN, Site
    from sqlalchemy import func

    stmt = select(VLAN)
    if site:
        site_obj = db.scalar(select(Site).where(Site.code == site))
        if site_obj:
            stmt = stmt.where(VLAN.site_id == site_obj.id)

    vlans = db.execute(stmt.order_by(VLAN.site_id, VLAN.vlan_id)).scalars().all()
    
    data = []
    # Pre-fetch site codes to avoid N+1 issues
    sites = {s.id: s.code for s in db.execute(select(Site)).scalars().all()}

    for v in vlans:
        network = ip_network(v.cidr, strict=False)
        total_ips = network.num_addresses
        usable_ips = total_ips - 2 if total_ips > 2 else total_ips
        
        allocated_count = db.scalar(
            select(func.count(IPAddress.id)).where(IPAddress.vlan_ref == v.id)
        ) or 0
        
        free_ips = usable_ips - allocated_count
        
        data.append({
            'Site': sites.get(v.site_id, str(v.site_id)),
            'VLAN ID': v.vlan_id,
            'Name': v.name or '',
            'CIDR': str(v.cidr),
            'Gateway': str(v.gateway) if v.gateway else '',
            'Description': v.description or '',
            'Allocated IPs': allocated_count,
            'Free IPs': free_ips,
            'Total Usable IPs': usable_ips
        })

    df = pd.DataFrame(data)
    actor = actor_from_user(user)
    audit(db, actor, 'EXPORT', 'vlan', None, None, {'fmt': fmt, 'site': site, 'rows': len(df)})
    db.commit()

    if fmt.lower() == 'xlsx':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='vlans')
        output.seek(0)
        return StreamingResponse(output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=vlan_export.xlsx'})

    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type='text/csv',
                             headers={'Content-Disposition': 'attachment; filename=vlan_export.csv'})

