from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from datetime import datetime
from typing import Optional
import csv
import json
import io

from app.db import get_session
from app.models import AuditLog
from app.deps import require_admin

router = APIRouter(prefix='/api/audit', tags=['audit'])

@router.get('/logs')
def get_audit_logs(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get audit logs with optional filters (admin only)"""
    query = select(AuditLog)
    
    filters = []
    
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filters.append(AuditLog.event_time >= dt)
        except:
            pass
    
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filters.append(AuditLog.event_time <= dt)
        except:
            pass
    
    if actor:
        filters.append(AuditLog.actor.ilike(f'%{actor}%'))
    
    if action:
        filters.append(AuditLog.action == action)
    
    if entity:
        filters.append(AuditLog.entity == entity)
    
    if filters:
        query = query.where(and_(*filters))
    
    query = query.order_by(AuditLog.event_time.desc()).limit(limit).offset(offset)
    
    logs = db.scalars(query).all()
    
    # Count total for pagination
    from sqlalchemy import func
    count_query = select(func.count(AuditLog.id))
    if filters:
        count_query = count_query.where(and_(*filters))
    total = db.scalar(count_query) or 0
    
    return {
        'logs': [
            {
                'id': log.id,
                'event_time': log.event_time.isoformat(),
                'actor': log.actor,
                'action': log.action,
                'entity': log.entity,
                'entity_id': log.entity_id,
                'old_value': log.old_value,
                'new_value': log.new_value
            }
            for log in logs
        ],
        'total': total,
        'limit': limit,
        'offset': offset
    }

@router.get('/export/csv')
def export_audit_logs_csv(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None
):
    """Export audit logs as CSV (admin only)"""
    query = select(AuditLog)
    
    filters = []
    
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filters.append(AuditLog.event_time >= dt)
        except:
            pass
    
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filters.append(AuditLog.event_time <= dt)
        except:
            pass
    
    if actor:
        filters.append(AuditLog.actor.ilike(f'%{actor}%'))
    
    if action:
        filters.append(AuditLog.action == action)
    
    if entity:
        filters.append(AuditLog.entity == entity)
    
    if filters:
        query = query.where(and_(*filters))
    
    query = query.order_by(AuditLog.event_time.desc())
    logs = db.scalars(query).all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Event Time', 'Actor', 'Action', 'Entity', 'Entity ID', 'Old Value', 'New Value'])
    
    # Write rows
    for log in logs:
        writer.writerow([
            log.id,
            log.event_time.isoformat(),
            log.actor or '',
            log.action,
            log.entity,
            log.entity_id or '',
            json.dumps(log.old_value) if log.old_value else '',
            json.dumps(log.new_value) if log.new_value else ''
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename=audit_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )

@router.get('/export/json')
def export_audit_logs_json(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None
):
    """Export audit logs as JSON (admin only)"""
    query = select(AuditLog)
    
    filters = []
    
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filters.append(AuditLog.event_time >= dt)
        except:
            pass
    
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filters.append(AuditLog.event_time <= dt)
        except:
            pass
    
    if actor:
        filters.append(AuditLog.actor.ilike(f'%{actor}%'))
    
    if action:
        filters.append(AuditLog.action == action)
    
    if entity:
        filters.append(AuditLog.entity == entity)
    
    if filters:
        query = query.where(and_(*filters))
    
    query = query.order_by(AuditLog.event_time.desc())
    logs = db.scalars(query).all()
    
    # Create JSON
    logs_data = [
        {
            'id': log.id,
            'event_time': log.event_time.isoformat(),
            'actor': log.actor,
            'action': log.action,
            'entity': log.entity,
            'entity_id': log.entity_id,
            'old_value': log.old_value,
            'new_value': log.new_value
        }
        for log in logs
    ]
    
    json_str = json.dumps(logs_data, indent=2)
    
    return StreamingResponse(
        io.BytesIO(json_str.encode('utf-8')),
        media_type='application/json',
        headers={'Content-Disposition': f'attachment; filename=audit_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
    )

@router.get('/actions')
def get_available_actions(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Get list of available actions for filtering"""
    actions = db.execute(select(AuditLog.action).distinct()).scalars().all()
    return {'actions': sorted(actions)}

@router.get('/entities')
def get_available_entities(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Get list of available entities for filtering"""
    entities = db.execute(select(AuditLog.entity).distinct()).scalars().all()
    return {'entities': sorted(entities)}
