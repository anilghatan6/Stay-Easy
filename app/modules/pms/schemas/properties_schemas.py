import uuid
import uuid
import re
from datetime import datetime, time, date, timedelta
from decimal import Decimal
from typing import Annotated, Any, List, Optional
from typing_extensions import Self
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_validator,
    model_validator,
    EmailStr,
)

from app.modules.pms.models.properties_model import PropertyType

MAX_IMAGES_PER_PROPERTY = 20


class TimestampSchema(BaseModel):
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GeneralPropertyInfo(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        title="Property Name",
        description="Name of the property",
    )
    type: PropertyType = Field(
        title="property type",
        default=PropertyType.HOTEL,
        description="Type of the property",
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        title="Description",
        description="Description of the property",
    )
    total_rooms: int = Field(
        default=1,
        ge=1,
        le=10000,
        title="Total Rooms",
        description="Total number of rooms",
    )
    year_built: Optional[int] = Field(
        None,
        ge=1800,
        le=2100,
        title="Year Built",
        description="Year when the property was built",
    )
    number_of_floors: int = Field(
        default=1,
        ge=1,
        le=1000,
        title="Number of Floors",
        description="Number of floors in the property",
    )

    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=10,
        title="Phone Number",
        description="Phone number of the property owner for the property",
    )
    email: EmailStr = Field(
        ...,
        title="Email",
        description="Email of the property owner for the property",
    )

    @field_validator("phone_number")
    @classmethod
    def verify_phone_number(cls, value: str) -> str:
        value = value.strip()
        if " " in value:
            raise ValueError("Phone number must not contain spaces.")
        if not value.isdigit():
            raise ValueError("Phone number must contain only digits.")
        if len(value) != 10:
            raise ValueError("Phone number must be 10 digits.")
        return value

    @field_validator("name")
    @classmethod
    def clean_and_verify_name(cls, value: str) -> str:
        value = value.strip()
        return value

    @field_validator("email", mode="before")
    @classmethod
    def pre_strip_email(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value


class GeneralPropertyInfoResponse(GeneralPropertyInfo, TimestampSchema):
    id: uuid.UUID


class Location(BaseModel):
    country: str = Field(
        ...,
        min_length=2,
        max_length=100,
        title="Country",
        description="Country of the property",
    )
    state: str = Field(
        ...,
        min_length=2,
        max_length=100,
        title="State",
        description="State of the property",
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        title="City",
        description="City of the property",
    )
    zip_code: str = Field(
        ...,
        min_length=2,
        max_length=10,
        title="Zip Code",
        description="Zip code of the property",
    )
    address: str = Field(
        ...,
        min_length=2,
        max_length=255,
        title="Address",
        description="Address of the property",
    )
    latitude: Optional[Decimal] = Field(
        None,
        max_digits=9,
        decimal_places=6,
        title="Latitude",
        description="Latitude of the property",
    )
    longitude: Optional[Decimal] = Field(
        None,
        max_digits=9,
        decimal_places=6,
        title="Longitude",
        description="Longitude of the property",
    )


class LocationResponse(Location):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


class CustomAmenityItem(BaseModel):
    name: str = Field(
        ..., min_length=2, max_length=100, description="Name of the custom amenity"
    )
    icon: Optional[str] = Field(
        None, max_length=50, description="Icon code (e.g. 'fa-wifi')"
    )


class PhotoCollection(BaseModel):
    cover: Optional[str] = Field(
        None, description="The primary cover image URL. If None, no cover is set."
    )
    gallery: List[str] = Field(
        default_factory=list, description="List of secondary image URLs."
    )

    @model_validator(mode="after")
    def validate_gallery_limit(self):
        # Optional: Prevent users from uploading 500 images and crashing your UI
        if len(self.gallery) > 20:
            raise ValueError("Gallery cannot contain more than 20 images.")
        return self


class PropertyAmenity(BaseModel):
    system_amenity_ids: List[uuid.UUID] = Field(
        default_factory=list, description="List of system-provided amenity IDs"
    )
    custom_amenities: List[CustomAmenityItem] = Field(
        default_factory=list, description="List of user-defined custom amenities"
    )


class PropertyPhotosAndAmenities(BaseModel):
    photos: PhotoCollection = Field(default_factory=PhotoCollection)
    amenities: PropertyAmenity = Field(default_factory=PropertyAmenity)


class PropertyPhotosAndAmenitiesResponse(BaseModel):
    id: uuid.UUID
    photos: PhotoCollection
    amenities: PropertyAmenity
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def reconstruct_from_orm(cls, data):
        # When data comes from an ORM object (not a dict), convert it
        if not isinstance(data, dict):
            photos_raw = getattr(data, "photos", None) or {}
            return {
                "id": data.id,
                "photos": photos_raw,
                "amenities": {
                    "system_amenity_ids": getattr(data, "system_amenity_ids", []) or [],
                    "custom_amenities": getattr(data, "custom_amenities", []) or [],
                },
            }
        return data


class Propertylocalization(BaseModel):
    currency: str = Field(
        default="NPR",
        min_length=3,
        max_length=20,
        title="Currency",
        description="Currency of the property",
    )
    timezone: str = Field(
        default="UTC",
        min_length=3,
        max_length=100,
        title="Timezone",
        description="Timezone of the tenant",
    )

    language: str = Field(
        default="English",
        min_length=2,
        max_length=50,
        title="Language",
        description="Language of the property",
    )

    check_in_time: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=8,
        title="Check In Time",
        description="Check in time of the property",
    )

    check_out_time: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=8,
        title="Check Out Time",
        description="Check out time of the property",
    )
    check_in_grace_period: int = Field(
        default=0,
        le=60,
        ge=0,
        title="Check In Grace Period",
        description="Check in grace period of the property",
    )

    check_out_grace_period: int = Field(
        default=0,
        le=60,
        ge=0,
        title="Check Out Grace Period",
        description="Check out grace period of the property",
    )
    always_allow_check_in_out: bool = Field(
        default=False,
        title="Always Allow Check In and Check Out",
        description="Always allow check in and check out of the property",
    )

    # @field_validator("timezone", mode="before")
    # @classmethod
    # def validate_timezone(cls, value: str) -> str:
    #     try:
    #         ZoneInfo(value)
    #         return value
    #     except Exception:
    #         raise ValueError(
    #             f"'{value}' is not a valid IANA timezone name (e.g., 'Asia/Kathmandu')"
    #         )

    @model_validator(mode="after")
    def validate_check_in_out_time(self) -> Self:
        always_allow = self.always_allow_check_in_out
        has_check_in = self.check_in_time is not None
        has_check_out = self.check_out_time is not None

        if always_allow:
            if has_check_in or has_check_out:
                raise ValueError(
                    "Check in time and check out time must be None when always allow check in and check out is On"
                )
        else:
            if not has_check_in or not has_check_out:
                raise ValueError(
                    "Check in time and check out time are required when always allow check in and check out is Off"
                )

        return self


class PropertylocalizationResponse(Propertylocalization):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


class BrandVisual(BaseModel):
    brand_logo_url: str = Field(
        None,
        max_length=2048,
        title="Brand Logo URL",
        description="URL of the brand logo",
    )
    brand_color: str = Field(
        None,
        min_length=3,
        max_length=7,
        title="Brand Color",
        description="Color of the brand",
    )


class BrandVisualResponse(BrandVisual):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


class SystemAmenityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str = Field(..., max_length=100, description="The master amenity name")
    icon: Optional[str] = Field(
        None, max_length=100, description="The UI icon slug string"
    )


class PropertyPhotos(BaseModel):
    cover: Optional[str] = None
    gallery: List[str] = Field(default_factory=list)


# --- Base Property Schema for Data Output ---
class PropertyResponse(BaseModel):
    # Enable Pydantic to read directly from SQLAlchemy models ORM attributes
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str = Field(..., max_length=255)
    type: PropertyType
    description: Optional[str] = Field(None, max_length=2000)

    # Geo-location
    country: Optional[str] = Field(None, max_length=255)
    state: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=255)
    zip_code: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    latitude: Optional[Decimal] = Field(None, max_digits=9, decimal_places=6)
    longitude: Optional[Decimal] = Field(None, max_digits=9, decimal_places=6)

    # Operations & Policies
    check_in_time: Optional[str] = Field(None, max_length=20)
    check_out_time: Optional[str] = Field(None, max_length=20)
    check_in_grace_period: int = Field(default=0, ge=0)
    check_out_grace_period: int = Field(default=0, ge=0)
    always_allow_check_in_out: bool = False
    number_of_floors: int = Field(default=1, ge=1)
    total_rooms: int = Field(default=1, ge=1)
    year_built: Optional[int] = Field(None, ge=1800, le=2100)

    # Contact
    phone_number: Optional[str] = Field(None, max_length=15)
    email: Optional[EmailStr] = None  # Validates email format

    # Localization & Branding
    currency: str = Field(default="USD", max_length=3)
    timezone: str = Field(default="UTC", max_length=100)
    language: Optional[str] = Field(None, max_length=100)
    brand_logo_url: Optional[str] = Field(None, max_length=2048)
    brand_color: Optional[str] = Field(None, max_length=20)

    is_active: bool

    # Amenities & Media
    system_amenities: List[SystemAmenityResponse] = Field(default_factory=list)
    custom_amenities: List[dict[str, Any]] = Field(default_factory=list)
    photos: PropertyPhotos


# --- Bulk Retrieval Schema ---
class TenantPropertiesListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    total_count: int
    properties: List[PropertyResponse]


class SystemAmenitiesListResponse(BaseModel):
    total_count: int
    amenities: List[SystemAmenityResponse]
