from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from app.db import get_session
from app.models import IPAddress, Site, VLAN
from app.security import require_user
import ipaddress

router = APIRouter(prefix='/api/dashboard', tags=['dashboard'])

@router.get('/stats')
def get_dashboard_stats(db: Session = Depends(get_session), user=Depends(require_user)):
    """Get IP allocation statistics for all sites based on VLAN CIDRs"""
    
    # Get all sites
    sites = db.scalars(select(Site)).all()
    
    site_stats = []
    
    for site in sites:
        # Get all VLANs for this site
        vlans = db.scalars(select(VLAN).where(VLAN.site_id == site.id)).all()
        
        # Calculate total IPs from VLAN CIDRs
        total_ips = 0
        for vlan in vlans:
            try:
                network = ipaddress.ip_network(str(vlan.cidr))
                # Subtract network and broadcast addresses for usable IPs
                total_ips += network.num_addresses - 2  # -2 for network and broadcast
            except:
                pass  # Skip invalid CIDRs
        
        # Count allocated IPs in this site's VLANs
        # An IP belongs to a site if it's in one of that site's VLANs
        allocated = 0
        reserved = 0
        
        for vlan in vlans:
            # Count IPs that fall within this VLAN's CIDR
            result = db.execute(text('''
                SELECT 
                    COUNT(CASE WHEN status = 'allocated' THEN 1 END) as allocated_count,
                    COUNT(CASE WHEN status = 'reserved' THEN 1 END) as reserved_count
                FROM ip_address
                WHERE ip <<= CAST(:cidr AS cidr)
            '''), {'cidr': str(vlan.cidr)}).first()
            
            if result:
                allocated += result.allocated_count or 0
                reserved += result.reserved_count or 0
        
        # Free IPs = Total (from CIDR) - Allocated - Reserved
        free = max(0, total_ips - allocated - reserved)
        
        # Calculate utilization percentage based on allocated IPs
        utilization = round((allocated / total_ips * 100), 1) if total_ips > 0 else 0
        
        site_stats.append({
            'code': site.code,
            'name': site.name,
            'total': total_ips,
            'allocated': allocated,
            'reserved': reserved,
            'free': free,
            'utilizationPercent': utilization
        })
    
    return {'sites': site_stats}
