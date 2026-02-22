# IPAM Manager (Postgres + OIDC + VLAN + Bulk + Export)

A lightweight IP management web app:
- IP + hostname mapping with **history** (assignment versions)
- **Audit log** of changes
- VLANs with **CIDR auto-mapping**
- Local + OIDC login (session) + optional Bearer JWT for API
- Bulk upsert (CSV/XLSX)
- Export (CSV/XLSX)

## Run
```bash
docker compose up -d
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with Omnissa details
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

UI: http://localhost:8000/
Swagger: http://localhost:8000/docs

## Notes
- Admin operations (VLAN CRUD + bulk) require the user to have `ADMIN_GROUP` in OIDC `groups` claim.
- In production, use HTTPS and set `https_only=True`.
"# ipam" 
