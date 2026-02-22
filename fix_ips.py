import os
import sys

# Add app to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal
from app.models import IPAddress
from app.utils import infer_site_code
from app.crud import get_site_id, infer_vlan_ref

def fix_ips():
    db = SessionLocal()
    try:
        ips = db.query(IPAddress).all()
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
                print(f"IP {ip.ip}: Site changing from {ip.site_id} to {correct_site_id} ({correct_site_code})")
                ip.site_id = correct_site_id
                needs_update = True
                
            if ip.vlan_ref != correct_vlan_ref:
                print(f"IP {ip.ip}: VLAN ref changing from {ip.vlan_ref} to {correct_vlan_ref}")
                ip.vlan_ref = correct_vlan_ref
                needs_update = True
                
            if needs_update:
                fixed_count += 1
                
        if fixed_count > 0:
            db.commit()
            print(f"Successfully fixed {fixed_count} IP records.")
        else:
            print("All IP records are already correct. No fixes needed.")
    except Exception as e:
        print(f"Error during execution: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    fix_ips()
