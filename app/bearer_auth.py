import os
import time
import httpx
from jose import jwt
from jose.exceptions import JWTError
from fastapi import HTTPException

_cache = {'jwks': None, 'expires': 0.0, 'issuer': None, 'aud': None, 'algs': None}


def _audience():
    return os.getenv('OIDC_AUDIENCE') or os.getenv('OIDC_CLIENT_ID')

async def _load_metadata():
    url = os.getenv('OIDC_DISCOVERY_URL')
    if not url:
        raise HTTPException(status_code=500, detail='OIDC_DISCOVERY_URL not configured')
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()

async def _get_jwks():
    now = time.time()
    if _cache['jwks'] and now < _cache['expires']:
        return _cache['jwks']

    meta = await _load_metadata()
    jwks_uri = meta.get('jwks_uri')
    issuer = meta.get('issuer')
    if not jwks_uri or not issuer:
        raise HTTPException(status_code=500, detail='OIDC metadata missing jwks_uri/issuer')

    _cache['issuer'] = issuer
    _cache['aud'] = _audience()
    _cache['algs'] = meta.get('id_token_signing_alg_values_supported') or ['RS256']

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(jwks_uri)
        r.raise_for_status()
        _cache['jwks'] = r.json()
        _cache['expires'] = now + 3600
        return _cache['jwks']

async def validate_bearer(auth_header: str) -> dict:
    if not auth_header or not auth_header.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Missing bearer token')

    token = auth_header.split(' ', 1)[1].strip()
    jwks = await _get_jwks()

    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=_cache.get('algs') or ['RS256'],
            audience=_cache.get('aud'),
            issuer=_cache.get('issuer'),
            options={'verify_aud': True, 'verify_iss': True, 'verify_exp': True},
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f'Invalid token: {e}')

    return {
        'sub': claims.get('sub'),
        'email': claims.get('email'),
        'name': claims.get('name'),
        'groups': claims.get('groups', []),
        'claims': claims,
    }
