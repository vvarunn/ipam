from fastapi import HTTPException, Request
from .utils import is_admin

def require_admin(request: Request):
    """Dependency that requires admin privileges"""
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')
    if not is_admin(user):
        raise HTTPException(status_code=403, detail='Admin privileges required')
    return user

def get_current_user(request: Request):
    """Get current user from session, raise 401 if not authenticated"""
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail='Authentication required')
    return user
