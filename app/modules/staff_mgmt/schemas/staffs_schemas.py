import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

from app.modules.staff_mgmt.models.staffs_model import JobRole, StaffStatus
from app.config.settings_config import settings

CLOUDINARY_BASE = settings.CLOUDINARY_BASE



class StaffPhotos(BaseModel):
    profile: Optional[str] = None
    citizenship_front: Optional[str] = None
    citizenship_back: Optional[str] = None

    @field_validator("profile", "citizenship_front", "citizenship_back")
    @classmethod
    def validate_cloudinary_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v

        url = v.strip()

        if not url:
            return None  

        if not url.startswith(CLOUDINARY_BASE):
            raise ValueError(
                "Invalid image format."
            )

        return url


# ─── CREATE ──────────────────────────────────────

class CreateStaffRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255,title="Full Name")
    email: EmailStr=Field(...,title="Email")
    phone_number: Optional[str] = Field(default=None, max_length=20,title="Phone Number")
    job_role: JobRole=Field(...,title="Job Role")
    monthly_salary: Decimal = Field(...,title="Monthly Salary", gt=0, le = 10000000, decimal_places=2)
    joining_date: date=Field(...,title="Joining Date")
    status: StaffStatus = StaffStatus.ACTIVE 
    photos: Optional[StaffPhotos] = None


    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
            
        if not v.strip():
            raise ValueError("Phone number cannot be blank if provided")

        if not v.strip().isdigit():
            raise ValueError("Phone number must contain only digits")
            
        return v.strip()

  

# ─── UPDATE ──────────────────────────────────────

class UpdateStaffRequest(BaseModel):
    """
    All fields optional — only provided fields get updated (partial update / PATCH semantics).
    property_ids, if provided, REPLACES the full set of property assignments.
    """
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255,title="Full Name")
    email: Optional[EmailStr] = Field(default=None,title="Email")
    phone_number: Optional[str] = Field(default=None, max_length=20,title="Phone Number")
    job_role: Optional[JobRole] = Field(default=None,title="Job Role")
    monthly_salary: Optional[Decimal] = Field(default=None,title="Monthly Salary", gt=0,le=100000000, decimal_places=2)
    joining_date: Optional[date] = Field(default=None,title="Joining Date")
    status: Optional[StaffStatus] = Field(default=None,title="Status")
    photos: Optional[StaffPhotos] = Field(default=None,title="Photos")

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
            
        if not v.strip():
            raise ValueError("Phone number cannot be blank if provided")

        if not v.strip().isdigit():
            raise ValueError("Phone number must contain only digits")
            
        return v.strip()



# ─── RESPONSE ──────────────────────────────────────

class StaffResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    full_name: str
    email: str
    phone_number: Optional[str]
    job_role: JobRole
    monthly_salary: Decimal
    joining_date: date
    status: StaffStatus
    photos: StaffPhotos

    model_config = ConfigDict(from_attributes=True)


