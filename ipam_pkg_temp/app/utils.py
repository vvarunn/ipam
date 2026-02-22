import os
import ipaddress

UAT_SUBNETS = [
    ipaddress.ip_network('100.112.13.160/28'),
    ipaddress.ip_network('100.112.4.128/26'),
    ipaddress.ip_network('100.112.4.192/26'),
    ipaddress.ip_network('100.112.4.32/27'),
    ipaddress.ip_network('100.112.4.64/26'),
    ipaddress.ip_network('100.112.5.0/27'),
    ipaddress.ip_network('100.112.5.128/27'),
    ipaddress.ip_network('100.112.5.32/27'),
    ipaddress.ip_network('100.112.5.64/26'),
    ipaddress.ip_network('100.112.7.0/25')
]

def infer_site_code(ip: str) -> str:
    addr = ipaddress.ip_address(ip)
    
    for subnet in UAT_SUBNETS:
        if addr in subnet:
            return 'UAT'
            
    s = str(addr)
    
    if s.startswith('100.140.') or s.startswith('100.130.'):
        return 'DC'
    if s.startswith('100.141.') or s.startswith('100.131.'):
        return 'DR'

    dc_prefix = os.getenv('DC_PREFIX', '100.121.')
    dr_prefix = os.getenv('DR_PREFIX', '100.112.')
    
    if s.startswith(dc_prefix):
        return 'DC'
    if s.startswith(dr_prefix):
        return 'DR'
        
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
