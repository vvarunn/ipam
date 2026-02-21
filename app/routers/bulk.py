import io
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_session
from ..models import IPAddress, VLAN, Site
from ..security import require_user
from ..deps import require_admin
from ..utils import actor_from_user
from ..crud import create_ip_with_assignment, update_ip_hostname, audit

router = APIRouter(prefix='/api/bulk', tags=['bulk'])

@router.post('/upsert')
async def bulk_upsert(file: UploadFile = File(...), db: Session = Depends(get_session), user=Depends(require_admin)):
    content = await file.read()

    if file.filename.lower().endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    elif file.filename.lower().endswith('.xlsx'):
        df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
    else:
        raise HTTPException(400, 'Only CSV or XLSX supported')

    if 'ip' not in df.columns:
        raise HTTPException(400, 'Missing required column: ip')

    actor = actor_from_user(user)
    results = {'created': 0, 'updated': 0, 'errors': []}

    for idx, row in df.iterrows():
        try:
            ip = str(row['ip']).strip()
            hostname = str(row.get('hostname') or '').strip() or None
            label = str(row.get('label') or '').strip() or None
            notes = str(row.get('notes') or '').strip() or None
            status = str(row.get('status') or '').strip() or None

            vlan_id = row.get('vlan_id')
            vlan_id = int(vlan_id) if str(vlan_id).strip() not in ('', 'nan', 'None') else None

            existing = db.scalar(select(IPAddress).where(IPAddress.ip == ip))
            if not existing:
                create_ip_with_assignment(db, ip=ip, hostname=hostname, actor=actor, label=label, notes=notes,
                                          status=status or 'allocated', vlan_numeric=vlan_id)
                results['created'] += 1
            else:
                update_ip_hostname(db, ip_id=existing.id, actor=actor, hostname=hostname, label=label, notes=notes,
                                   status=status, vlan_numeric=vlan_id)
                results['updated'] += 1

        except Exception as e:
            results['errors'].append({'row': int(idx), 'error': str(e)})
    
    # Log the bulk operation (each individual operation was already committed)
    try:
        audit(db, actor, 'BULK_UPSERT', 'bulk', None, None, {'file': file.filename, 'created': results['created'], 'updated': results['updated']})
        db.commit()
    except Exception as e:
        # If bulk audit fails, still return results since IPs were already committed
        pass
    
    return results

@router.post('/vlan-upsert')
async def bulk_vlan_upsert(file: UploadFile = File(...), db: Session = Depends(get_session), user=Depends(require_admin)):
    content = await file.read()

    if file.filename.lower().endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    elif file.filename.lower().endswith('.xlsx'):
        df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
    else:
        raise HTTPException(400, 'Only CSV or XLSX supported')

    required_columns = ['site_code', 'vlan_id', 'cidr']
    for col in required_columns:
        if col not in df.columns:
            raise HTTPException(400, f'Missing required column: {col}')

    actor = actor_from_user(user)
    results = {'created': 0, 'updated': 0, 'errors': []}

    for idx, row in df.iterrows():
        try:
            site_code = str(row['site_code']).strip()
            vlan_id = int(row['vlan_id'])
            cidr = str(row['cidr']).strip()
            name = str(row.get('name') or '').strip() or None
            gateway = str(row.get('gateway') or '').strip() or None
            description = str(row.get('description') or '').strip() or None

            # Get site
            site_obj = db.scalar(select(Site).where(Site.code == site_code))
            if not site_obj:
                results['errors'].append({'row': int(idx), 'error': f'Site {site_code} not found'})
                continue

            # Check if VLAN exists
            existing = db.scalar(select(VLAN).where(VLAN.site_id == site_obj.id, VLAN.vlan_id == vlan_id))
            
            if not existing:
                vlan = VLAN(
                    site_id=site_obj.id,
                    vlan_id=vlan_id,
                    name=name,
                    cidr=cidr,
                    gateway=gateway,
                    description=description,
                )
                db.add(vlan)
                db.flush()
                audit(db, actor, 'CREATE_VLAN', 'vlan', vlan.id, None, {
                    'site_code': site_code,
                    'vlan_id': vlan_id,
                    'cidr': cidr,
                    'name': name,
                    'gateway': gateway,
                    'description': description
                })
                db.commit()
                results['created'] += 1
            else:
                old = {
                    'name': existing.name,
                    'cidr': str(existing.cidr),
                    'gateway': str(existing.gateway) if existing.gateway else None,
                    'description': existing.description
                }
                if name:
                    existing.name = name
                if cidr:
                    existing.cidr = cidr
                if gateway:
                    existing.gateway = gateway
                if description:
                    existing.description = description
                
                audit(db, actor, 'UPDATE_VLAN', 'vlan', existing.id, old, {
                    'name': name,
                    'cidr': cidr,
                    'gateway': gateway,
                    'description': description
                })
                db.commit()
                results['updated'] += 1

        except Exception as e:
            results['errors'].append({'row': int(idx), 'error': str(e)})

    # Log the bulk operation
    try:
        audit(db, actor, 'BULK_VLAN_UPSERT', 'bulk', None, None, {
            'file': file.filename,
            'created': results['created'],
            'updated': results['updated']
        })
        db.commit()
    except Exception as e:
        pass
    
    return results
