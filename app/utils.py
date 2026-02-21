import os
import ipaddress

def infer_site_code(ip: str) -> str:
    dc_prefix = os.getenv('DC_PREFIX', '100.121.')
    dr_prefix = os.getenv('DR_PREFIX', '100.112.')
    uat_prefix = os.getenv('UAT_PREFIX', '100.130.')
    addr = ipaddress.ip_address(ip)
    s = str(addr)
    if s.startswith(dc_prefix):
        return 'DC'
    if s.startswith(dr_prefix):
        return 'DR'
    if s.startswith(uat_prefix):
        return 'UAT'
    return 'DC'

def actor_from_user(user: dict | None) -> str:
    if not user:
        return 'unknown'
    return user.get('email') or user.get('name') or user.get('sub') or 'unknown'

def is_admin(user: dict | None) -> bool:
    if not user:
        return False
    admin_group = os.getenv('ADMIN_GROUP', 'IPAM-Admins')
    groups = user.get('groups') or []
    return admin_group in groups
