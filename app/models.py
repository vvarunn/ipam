from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, ForeignKey, DateTime, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import INET, CIDR, JSONB
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class Site(Base):
    __tablename__ = 'site'
    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(50), nullable=False)

class VLAN(Base):
    __tablename__ = 'vlan'
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey('site.id'), nullable=False)
    vlan_id = Column(Integer, nullable=False)
    name = Column(String(100))
    cidr = Column(CIDR, nullable=False)
    gateway = Column(INET)
    description = Column(String)
    __table_args__ = (UniqueConstraint('site_id', 'vlan_id', name='uq_vlan_site_vlan'),)

class IPAddress(Base):
    __tablename__ = 'ip_address'
    id = Column(Integer, primary_key=True)
    ip = Column(INET, nullable=False)
    site_id = Column(Integer, ForeignKey('site.id'), nullable=False)
    vlan_ref = Column(Integer, ForeignKey('vlan.id'))
    status = Column(String(20), nullable=False, default='allocated')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint('ip', 'site_id', name='uq_ip_site'),)

class IPAssignment(Base):
    __tablename__ = 'ip_assignment'
    id = Column(Integer, primary_key=True)
    ip_id = Column(Integer, ForeignKey('ip_address.id', ondelete='CASCADE'), nullable=False)
    hostname = Column(String(255))
    label = Column(String(50))
    notes = Column(String)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_by = Column(String(100))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class AuditLog(Base):
    __tablename__ = 'audit_log'
    id = Column(BigInteger, primary_key=True)
    event_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor = Column(String(100))
    action = Column(String(50), nullable=False)
    entity = Column(String(50), nullable=False)
    entity_id = Column(BigInteger)
    old_value = Column(JSONB)
    new_value = Column(JSONB)

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_admin = Column(Boolean, nullable=False, default=False)
    is_readonly = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    groups = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Settings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    encrypted = Column(Boolean, nullable=False, default=False)
    updated_by = Column(String(100))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
