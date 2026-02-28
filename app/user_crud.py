from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import User
from .password import hash_password

def create_user(db: Session, username: str, password: str, email: str | None = None, 
                full_name: str | None = None, is_admin: bool = False, is_readonly: bool = False) -> User:
    """Create a new user with hashed password."""
    # Check if user already exists
    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        raise ValueError(f'User {username} already exists')
    
    if email:
        existing_email = db.scalar(select(User).where(User.email == email))
        if existing_email:
            raise ValueError(f'Email {email} already in use')
    
    # Create user
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_admin=is_admin,
        is_readonly=is_readonly,
        is_active=True,
        groups=[]
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

def ensure_admin_user(db: Session, username: str, password: str, email: str | None = None):
    """Ensure an admin user exists, create or update if needed."""
    existing = db.scalar(select(User).where(User.username == username))
    if not existing:
        create_user(db, username=username, password=password, email=email, 
                   full_name='Administrator', is_admin=True)
        print(f'Created admin user: {username}')
    else:
        # Reset password to ensure ENV password works
        # Bcrypt has 72 byte limit
        if len(password) > 72:
            print(f"WARNING: Admin password too long ({len(password)}). Truncating to 72 bytes.")
            password = password[:72]
            
        existing.hashed_password = hash_password(password)
        if email and not existing.email:
            existing.email = email
        existing.is_admin = True
        db.commit()
        print(f'Updated admin user password: {username}')
