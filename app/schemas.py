from pydantic import BaseModel, Field
from typing import Optional

class IPCreate(BaseModel):
    ip: str
    hostname: Optional[str] = None
    label: Optional[str] = None
    notes: Optional[str] = None
    status: str = 'allocated'
    vlan_id: Optional[int] = None
    actor: Optional[str] = Field(default=None)

class HostnameUpdate(BaseModel):
    hostname: Optional[str] = None
    label: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    vlan_id: Optional[int] = None
    actor: Optional[str] = Field(default=None)

class VlanCreate(BaseModel):
    site_code: str
    vlan_id: int
    name: Optional[str] = None
    cidr: str
    gateway: Optional[str] = None
    description: Optional[str] = None

class VlanUpdate(BaseModel):
    name: Optional[str] = None
    cidr: Optional[str] = None
    gateway: Optional[str] = None
    description: Optional[str] = None

class PublicIPCreate(BaseModel):
    public_ip: str
    private_ip: Optional[str] = None
    fqdn: Optional[str] = None
    owner: Optional[str] = None
    status: str = 'allocated'
    notes: Optional[str] = None
    actor: Optional[str] = Field(default=None)

class PublicIPUpdate(BaseModel):
    private_ip: Optional[str] = None
    fqdn: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    actor: Optional[str] = Field(default=None)

