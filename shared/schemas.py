from datetime import date
from typing import Optional

from pydantic import BaseModel


class ClaimBase(BaseModel):
    claim_id: str
    encounter_type: Optional[str] = None
    service_date: Optional[date] = None
    national_id: Optional[str] = None
    member_id: Optional[str] = None
    facility_id: Optional[str] = None
    unique_id: Optional[str] = None
    diagnosis_codes: Optional[str] = None
    service_code: Optional[str] = None
    paid_amount_aed: Optional[float] = None
    approval_number: Optional[str] = None
    status: Optional[str] = None
    error_type: Optional[str] = None
    error_explanation: Optional[str] = None
    recommended_action: Optional[str] = None


class ClaimCreate(ClaimBase):
    pass


class Claim(ClaimBase):
    id: int

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class HealthCheck(BaseModel):
    status: str
    message: str
