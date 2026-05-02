from sqlalchemy.orm import Session
from sqlalchemy import select, or_, text, Text
from .models import Site, VLAN, IPAddress, IPAssignment, AuditLog, PublicIP
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
                              notes: str | None = None, status: str = 'allocated', vlan_numeric: int | None = None,
                              owner_name: str | None = None, app_name: str | None = None):
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

    if hostname or label or notes or owner_name or app_name:
        db.add(IPAssignment(ip_id=ip_obj.id, hostname=hostname, label=label, notes=notes,
                            owner_name=owner_name, app_name=app_name,
                            is_active=True, updated_by=actor))

    audit(db, actor, 'CREATE_IP', 'ip_address', ip_obj.id, None, {'ip': ip, 'site': site_code, 'vlan_ref': vlan_ref, 'status': status})
    db.commit()
    return ip_obj.id


def update_ip_hostname(db: Session, ip_id: int, actor: str, hostname: str | None = None, label: str | None = None,
                       notes: str | None = None, status: str | None = None, vlan_numeric: int | None = None,
                       owner_name: str | None = None, app_name: str | None = None):
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
        old_assign = {'hostname': current.hostname, 'label': current.label, 'notes': current.notes,
                      'owner_name': current.owner_name, 'app_name': current.app_name}
        current.is_active = False

    new_assign = IPAssignment(ip_id=ip_id, hostname=hostname, label=label, notes=notes,
                              owner_name=owner_name, app_name=app_name,
                              is_active=True, updated_by=actor)
    db.add(new_assign)
    db.flush()

    audit(db, actor, 'UPDATE_IP', 'ip_address', ip_id, old_ip, {'status': ip_obj.status, 'vlan_ref': ip_obj.vlan_ref})
    audit(db, actor, 'UPDATE_HOSTNAME', 'ip_assignment', new_assign.id, old_assign,
          {'hostname': hostname, 'label': label, 'notes': notes, 'owner_name': owner_name, 'app_name': app_name})
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

def fix_ip_sites_and_vlans(db: Session):
    try:
        ips = db.execute(select(IPAddress)).scalars().all()
        fixed_count = 0
        for ip in ips:
            correct_site_code = infer_site_code(str(ip.ip))
            try:
                correct_site_id = get_site_id(db, correct_site_code)
            except ValueError:
                continue
                
            correct_vlan_ref = infer_vlan_ref(db, correct_site_id, str(ip.ip))
            
            needs_update = False
            if ip.site_id != correct_site_id:
                ip.site_id = correct_site_id
                needs_update = True
                
            if ip.vlan_ref != correct_vlan_ref:
                ip.vlan_ref = correct_vlan_ref
                needs_update = True
                
            if needs_update:
                fixed_count += 1
                
        if fixed_count > 0:
            db.commit()
            print(f"Startup check: Successfully fixed/updated {fixed_count} IP records.")
    except Exception as e:
        print(f"Startup check: Error fixing IP sites and VLANs: {e}")
        db.rollback()


def search_public_ips(db: Session, q: str = '', status: str | None = None):
    stmt = select(PublicIP)
    
    if status:
        stmt = stmt.where(PublicIP.status == status)
        
    if q:
        like = f'%{q}%'
        stmt = stmt.where(or_(
            PublicIP.public_ip.cast(Text).ilike(like),
            PublicIP.private_ip.cast(Text).ilike(like),
            PublicIP.fqdn.ilike(like),
            PublicIP.owner.ilike(like),
            PublicIP.notes.ilike(like)
        ))
        
    results = db.execute(stmt.order_by(PublicIP.public_ip)).scalars().all()
    return results

def create_public_ip(db: Session, actor: str, public_ip: str, private_ip: str | None = None,
                     fqdn: str | None = None, owner: str | None = None, status: str = 'allocated',
                     notes: str | None = None):
    if db.scalar(select(PublicIP).where(PublicIP.public_ip == public_ip)):
        raise ValueError('Public IP already exists')

    ip_obj = PublicIP(
        public_ip=public_ip, 
        private_ip=private_ip, 
        fqdn=fqdn, 
        owner=owner, 
        status=status,
        notes=notes
    )
    db.add(ip_obj)
    db.flush()
    
    audit(db, actor, 'CREATE_PUBLIC_IP', 'public_ip', ip_obj.id, None, {
        'public_ip': public_ip, 'private_ip': private_ip, 'fqdn': fqdn, 'owner': owner, 'status': status
    })
    db.commit()
    return ip_obj.id

def update_public_ip(db: Session, actor: str, public_ip_id: int, private_ip: str | None = None,
                     fqdn: str | None = None, owner: str | None = None, status: str | None = None,
                     notes: str | None = None):
    ip_obj = db.get(PublicIP, public_ip_id)
    if not ip_obj:
        raise ValueError('Public IP not found')

    old_val = {
        'private_ip': ip_obj.private_ip,
        'fqdn': ip_obj.fqdn,
        'owner': ip_obj.owner,
        'status': ip_obj.status,
        'notes': ip_obj.notes
    }

    if private_ip is not None: ip_obj.private_ip = private_ip
    if fqdn is not None: ip_obj.fqdn = fqdn
    if owner is not None: ip_obj.owner = owner
    if status is not None: ip_obj.status = status
    if notes is not None: ip_obj.notes = notes

    db.flush()
    
    new_val = {
        'private_ip': ip_obj.private_ip,
        'fqdn': ip_obj.fqdn,
        'owner': ip_obj.owner,
        'status': ip_obj.status,
        'notes': ip_obj.notes
    }
    
    audit(db, actor, 'UPDATE_PUBLIC_IP', 'public_ip', ip_obj.id, old_val, new_val)
    db.commit()
    return ip_obj.id

def delete_public_ip(db: Session, actor: str, public_ip_id: int):
    ip_obj = db.get(PublicIP, public_ip_id)
    if not ip_obj:
        raise ValueError('Public IP not found')
        
    old_val = {
        'public_ip': str(ip_obj.public_ip),
        'private_ip': str(ip_obj.private_ip) if ip_obj.private_ip else None,
        'fqdn': ip_obj.fqdn,
        'owner': ip_obj.owner,
        'status': ip_obj.status
    }
    
    db.delete(ip_obj)
    audit(db, actor, 'DELETE_PUBLIC_IP', 'public_ip', public_ip_id, old_val, None)
    db.commit()

