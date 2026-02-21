from sqlalchemy.orm import Session
from sqlalchemy import select, or_, text, Text
from .models import Site, VLAN, IPAddress, IPAssignment, AuditLog
from .utils import infer_site_code


def ensure_sites(db: Session):
    for code, name in [('DC', 'Data Center'), ('DR', 'Disaster Recovery'), ('UAT', 'User Acceptance Testing')]:
        if not db.scalar(select(Site).where(Site.code == code)):
            db.add(Site(code=code, name=name))
    db.commit()


def ensure_indexes(db: Session):
    db.execute(text('''
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ip_assignment_active
        ON ip_assignment(ip_id)
        WHERE is_active = TRUE
    '''))
    db.execute(text('''
        CREATE INDEX IF NOT EXISTS idx_vlan_cidr_gist
        ON vlan USING GIST (cidr inet_ops)
    '''))
    db.commit()


def get_site_id(db: Session, code: str) -> int:
    site = db.scalar(select(Site).where(Site.code == code))
    if not site:
        raise ValueError(f'Site {code} not found')
    return site.id


def audit(db: Session, actor: str, action: str, entity: str, entity_id: int | None, old_value, new_value):
    db.add(AuditLog(actor=actor, action=action, entity=entity, entity_id=entity_id, old_value=old_value, new_value=new_value))


def infer_vlan_ref(db: Session, site_id: int, ip: str) -> int | None:
    return db.execute(text('''
        SELECT id FROM vlan
        WHERE site_id=:site_id AND cidr >>= CAST(:ip AS inet)
        ORDER BY masklen(cidr) DESC
        LIMIT 1
    '''), {'site_id': site_id, 'ip': ip}).scalar()


def find_vlan_by_numeric(db: Session, site_id: int, vlan_id: int) -> int | None:
    return db.scalar(select(VLAN.id).where(VLAN.site_id == site_id, VLAN.vlan_id == vlan_id))


def search(db: Session, q: str = '', site_code: str | None = None, vlan_id: int | None = None, status: str | None = None):
    stmt = (
        select(IPAddress, IPAssignment, Site, VLAN)
        .join(Site, Site.id == IPAddress.site_id)
        .join(IPAssignment, (IPAssignment.ip_id == IPAddress.id) & (IPAssignment.is_active == True), isouter=True)
        .join(VLAN, VLAN.id == IPAddress.vlan_ref, isouter=True)
    )

    if site_code:
        stmt = stmt.where(IPAddress.site_id == get_site_id(db, site_code))

    if vlan_id is not None:
        stmt = stmt.where(VLAN.vlan_id == vlan_id)

    if status:
        stmt = stmt.where(IPAddress.status == status)

    if q:
        like = f'%{q}%'
        stmt = stmt.where(or_(IPAddress.ip.cast(Text).ilike(like), IPAssignment.hostname.ilike(like)))

    results = db.execute(stmt.order_by(IPAddress.ip)).all()
    
    # Post-process to find VLAN by CIDR if vlan_ref is not set
    enhanced_results = []
    for ip_obj, assign, site, vlan in results:
        if not vlan:
            # Find VLAN by CIDR matching
            vlan = db.execute(text('''
                SELECT * FROM vlan
                WHERE site_id = :site_id AND cidr >>= CAST(:ip AS inet)
                ORDER BY masklen(cidr) DESC
                LIMIT 1
            '''), {'site_id': ip_obj.site_id, 'ip': str(ip_obj.ip)}).first()
            if vlan:
                # Convert row to VLAN object
                vlan = db.get(VLAN, vlan.id)
        enhanced_results.append((ip_obj, assign, site, vlan))
    
    return enhanced_results


def create_ip_with_assignment(db: Session, ip: str, hostname: str | None, actor: str, label: str | None = None,
                              notes: str | None = None, status: str = 'allocated', vlan_numeric: int | None = None):
    site_code = infer_site_code(ip)
    site_id = get_site_id(db, site_code)

    if db.scalar(select(IPAddress).where(IPAddress.ip == ip, IPAddress.site_id == site_id)):
        raise ValueError('IP already exists for this site')

    vlan_ref = find_vlan_by_numeric(db, site_id, vlan_numeric) if vlan_numeric is not None else None
    if vlan_ref is None:
        vlan_ref = infer_vlan_ref(db, site_id, ip)

    ip_obj = IPAddress(ip=ip, site_id=site_id, vlan_ref=vlan_ref, status=status)
    db.add(ip_obj)
    db.flush()

    if hostname or label or notes:
        db.add(IPAssignment(ip_id=ip_obj.id, hostname=hostname, label=label, notes=notes, is_active=True, updated_by=actor))

    audit(db, actor, 'CREATE_IP', 'ip_address', ip_obj.id, None, {'ip': ip, 'site': site_code, 'vlan_ref': vlan_ref, 'status': status})
    db.commit()
    return ip_obj.id


def update_ip_hostname(db: Session, ip_id: int, actor: str, hostname: str | None = None, label: str | None = None,
                       notes: str | None = None, status: str | None = None, vlan_numeric: int | None = None):
    ip_obj = db.get(IPAddress, ip_id)
    if not ip_obj:
        raise ValueError('IP not found')

    old_ip = {'status': ip_obj.status, 'vlan_ref': ip_obj.vlan_ref}

    if status:
        ip_obj.status = status

    if vlan_numeric is not None:
        ip_obj.vlan_ref = find_vlan_by_numeric(db, ip_obj.site_id, vlan_numeric)

    current = db.scalar(select(IPAssignment).where(IPAssignment.ip_id == ip_id, IPAssignment.is_active == True))
    old_assign = None
    if current:
        old_assign = {'hostname': current.hostname, 'label': current.label, 'notes': current.notes}
        current.is_active = False

    new_assign = IPAssignment(ip_id=ip_id, hostname=hostname, label=label, notes=notes, is_active=True, updated_by=actor)
    db.add(new_assign)
    db.flush()

    audit(db, actor, 'UPDATE_IP', 'ip_address', ip_id, old_ip, {'status': ip_obj.status, 'vlan_ref': ip_obj.vlan_ref})
    audit(db, actor, 'UPDATE_HOSTNAME', 'ip_assignment', new_assign.id, old_assign, {'hostname': hostname, 'label': label, 'notes': notes})
    db.commit()
    return new_assign.id


def ip_history(db: Session, ip_id: int):
    ip_obj = db.get(IPAddress, ip_id)
    if not ip_obj:
        raise ValueError('IP not found')

    assigns = db.execute(
        select(IPAssignment).where(IPAssignment.ip_id == ip_id).order_by(IPAssignment.updated_at.desc())
    ).scalars().all()
    return ip_obj, assigns
