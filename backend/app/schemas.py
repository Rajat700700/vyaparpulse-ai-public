"""Pydantic schemas exposed by API routes."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    enterprise_id: str
    enterprise_name: Optional[str] = None
    is_demo: bool = False
    display_name: Optional[str] = None
    access_token: Optional[str] = None


class EnterpriseOut(BaseModel):
    id: str
    name: str
    is_demo: bool
    analysis_as_of: Optional[datetime] = None


class KPICards(BaseModel):
    revenue_mtd_paise: int = 0
    outlets_at_risk: int = 0
    estimated_opportunity_paise: int = 0
    verified_recovery_paise: int = 0


class CommandCentreOut(BaseModel):
    enterprise: EnterpriseOut
    kpis: KPICards
    data_through: Optional[datetime] = None
    is_empty: bool = True
    empty_reason: str = "No data imported yet. Upload sales data to see recovery opportunities."


class MessageOut(BaseModel):
    message: str
