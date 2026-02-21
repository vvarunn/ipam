import io
import pandas as pd
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

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
