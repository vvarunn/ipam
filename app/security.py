from fastapi import Request, HTTPException
from .bearer_auth import validate_bearer

async def require_user(request: Request):
    user = request.session.get('user')
    if user:
        return user

    auth = request.headers.get('authorization')
    if auth:
        return await validate_bearer(auth)

    raise HTTPException(status_code=401, detail='Not authenticated')
