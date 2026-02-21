from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.db import get_session
from app.models import User
from app.deps import require_admin, get_current_user
from app.password import hash_password
from app.crud import audit

router = APIRouter(prefix='/api/users', tags=['users'])

class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    full_name: Optional[str] = None
    is_admin: bool = False

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    is_admin: bool
    is_active: bool
    
    class Config:
        from_attributes = True

@router.get('/', response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """List all users (admin only)"""
    users = db.scalars(select(User).order_by(User.username)).all()
    return users

@router.post('/', response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Create a new user (admin only)"""
    # Check if username already exists
    if db.scalar(select(User).where(User.username == user_data.username)):
        raise HTTPException(status_code=400, detail='Username already exists')
    
    # Check if email already exists
    if user_data.email and db.scalar(select(User).where(User.email == user_data.email)):
        raise HTTPException(status_code=400, detail='Email already exists')
    
    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        is_admin=user_data.is_admin,
        is_active=True
    )
    db.add(user)
    db.flush()
    
    audit(db, admin.get('username', 'admin'), 'CREATE_USER', 'user', user.id, None, {
        'username': user.username,
        'is_admin': user.is_admin
    })
    db.commit()
    
    return user

@router.put('/{user_id}', response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Update user details (admin only)"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    
    old_data = {
        'email': user.email,
        'full_name': user.full_name,
        'is_admin': user.is_admin,
        'is_active': user.is_active
    }
    
    # Update fields
    if user_data.email is not None:
        # Check email uniqueness
        existing = db.scalar(select(User).where(User.email == user_data.email, User.id != user_id))
        if existing:
            raise HTTPException(status_code=400, detail='Email already exists')
        user.email = user_data.email
    
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin
    
    db.flush()
    
    audit(db, admin.get('username', 'admin'), 'UPDATE_USER', 'user', user.id, old_data, {
        'email': user.email,
        'full_name': user.full_name,
        'is_admin': user.is_admin,
        'is_active': user.is_active
    })
    db.commit()
    
    return user

@router.delete('/{user_id}')
def delete_user(
    user_id: int,
    db: Session = Depends(get_session),
    admin: dict = Depends(require_admin)
):
    """Delete a user (admin only)"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    
    # Prevent deleting yourself
    if user.username == admin.get('username'):
        raise HTTPException(status_code=400, detail='Cannot delete your own account')
    
    audit(db, admin.get('username', 'admin'), 'DELETE_USER', 'user', user.id, {
        'username': user.username
    }, None)
    
    db.delete(user)
    db.commit()
    
    return {'ok': True, 'message': f'User {user.username} deleted'}
