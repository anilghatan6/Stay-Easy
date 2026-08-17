import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from app.modules.pms.models.rooms_model import CancellationPolicy, RoomStatus
from app.config.settings_config import settings

CLOUDINARY_BASE = settings.CLOUDINARY_BASE

# MAX_IMAGE_PER_ROOM = 10


class TimestampSchema(BaseModel):
    created_at: datetime
    updated_at: datetime


CANCELLATION_POLICY_DEFAULTS: Dict[CancellationPolicy, Dict[str, str]] = {
    CancellationPolicy.FLEXIBLE: {
        "title": "Flexible Cancellation",
        "description": "Full refund if cancelled up to 24 hours before check-in.",
    },
    CancellationPolicy.MODERATE: {
        "title": "Moderate Cancellation",
        "description": "Full refund if cancelled up to 5 days before check-in.",
    },
    CancellationPolicy.STRICT: {
        "title": "Strict Cancellation",
        "description": "50% refund if cancelled up to 1 week before check-in; no refund after that.",
    },
    CancellationPolicy.NON_REFUNDABLE: {
        "title": "Non-Refundable",
        "description": "No refund at any time after the booking is confirmed.",
    },
}


class RoomPhotos(BaseModel):
    """Matches the JSONB shape: {"cover": "url", "gallery": ["url1", ...]}"""

    cover: Optional[str] = Field(default=None)
    gallery: List[str] = Field(default_factory=list)

    @field_validator("gallery")
    @classmethod
    def limit_gallery_size(cls, v: List[str]) -> List[str]:
        if len(v) > 5:
            raise ValueError("You can't upload more than 5 photos.")
        return v

    @field_validator("cover", mode="before")
    @classmethod
    def validate_cover_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(CLOUDINARY_BASE):
            raise ValueError("Invalid Image Format.")
        return v

    @field_validator("gallery", mode="before")
    @classmethod
    def validate_gallery_urls(cls, v: List[str]) -> List[str]:
        if isinstance(v, list):
            for url in v:
                if not url.startswith(CLOUDINARY_BASE):
                    raise ValueError("Invalid Image Format.")
        return v


class CustomAmenity(BaseModel):
    """One inline custom amenity entry, e.g. from the 'Add a custom amenity' input."""

    name: str = Field(..., min_length=1, max_length=100)
    icon: Optional[str] = None


class RoomBase(BaseModel):
    floor_number: int = Field(
        ..., ge=0, le=100, description="Floor number (0 = ground floor)"
    )
    room_name: str = Field(
        ..., min_length=1, max_length=100, examples=["Ocean Suite A"]
    )
    room_type_id: uuid.UUID
    bed_type_id: uuid.UUID

    photos: RoomPhotos = Field(default_factory=RoomPhotos)

    max_adults: int = Field(2, ge=1, le=30)
    max_children: int = Field(0, ge=0, le=15)

    # RATES & POLICIES
    base_rate: Decimal = Field(
        ..., ge=1, decimal_places=2, description="Minimum rate per night (USD)"
    )
    status: RoomStatus = Field(
        RoomStatus.AVAILABLE, json_schema_extra={"nullable": False}
    )
    cancellation_policy: CancellationPolicy = CancellationPolicy.FLEXIBLE
    cancellation_title: Optional[str] = Field(None, max_length=255)
    cancellation_description: Optional[str] = Field(None, max_length=2000)

    # AMENITIES
    system_amenity_ids: List[uuid.UUID] = Field(default_factory=list)
    custom_amenities: List[CustomAmenity] = Field(default_factory=list)

    @model_validator(mode="after")
    def apply_cancellation_policy_defaults(self) -> "RoomBase":
        if self.cancellation_policy == CancellationPolicy.CUSTOM:
            if not (self.cancellation_title and self.cancellation_title.strip()):
                raise ValueError(
                    "cancellation title is required when cancellation policy is CUSTOM."
                )
            if not (
                self.cancellation_description and self.cancellation_description.strip()
            ):
                raise ValueError(
                    "cancellation description is required when cancellation policy is CUSTOM."
                )
        else:
            defaults = CANCELLATION_POLICY_DEFAULTS[self.cancellation_policy]
            self.cancellation_title = defaults["title"]
            self.cancellation_description = defaults["description"]
        return self


class RoomBulkCreateRequest(BaseModel):
    rooms: List[RoomBase] = Field(
        ..., min_length=1, max_length=50, description="List of rooms to be created"
    )

    @model_validator(mode="after")
    def no_duplicate_room_names_within_batch(self) -> "RoomBulkCreateRequest":
        names = [r.room_name.strip().lower() for r in self.rooms]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(
                f"Duplicate room name within this request: {', '.join(sorted(dupes))}"
            )
        return self


class RoomUpdate(BaseModel):
    room_name: Optional[str] = Field(
        None, min_length=1, max_length=100, examples=["Ocean Suite A"]
    )
    room_type_id: Optional[uuid.UUID] = None
    bed_type_id: Optional[uuid.UUID] = None
    photos: Optional[RoomPhotos] = None
    max_adults: Optional[int] = Field(None, ge=1, le=30)
    max_children: Optional[int] = Field(None, ge=0, le=15)
    floor_number: Optional[int] = Field(None, ge=0, le=100)
    base_rate: Optional[Decimal] = Field(None, ge=1, decimal_places=2)
    status: Optional[RoomStatus] = None
    cancellation_policy: Optional[CancellationPolicy] = None
    cancellation_title: Optional[str] = Field(None, max_length=255)
    cancellation_description: Optional[str] = Field(None, max_length=2000)
    system_amenity_ids: Optional[List[uuid.UUID]] = None
    custom_amenities: Optional[List[CustomAmenity]] = None

    @model_validator(mode="before")
    @classmethod
    def handle_cancellation_logic(cls, data: any) -> any:
        if not isinstance(data, dict):
            return data

        policy = data.get("cancellation_policy")
        title = data.get("cancellation_title")
        description = data.get("cancellation_description")

        if policy is not None:
            # 1. Handle CUSTOM logic with strict text checks
            if policy == CancellationPolicy.CUSTOM or policy == "CUSTOM":
                if not title or not str(title).strip():
                    raise ValueError(
                        "cancellation title is required when cancellation policy is CUSTOM."
                    )
                if not description or not str(description).strip():
                    raise ValueError(
                        "cancellation description is required when cancellation policy is CUSTOM."
                    )

            # 2. Automatically inject defaults for standard policies
            else:
                defaults = CANCELLATION_POLICY_DEFAULTS.get(policy)
                if defaults:
                    data["cancellation_title"] = defaults["title"]
                    data["cancellation_description"] = defaults["description"]

        return data


class RoomResponse(RoomBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID


class AmenityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    icon: Optional[str]


class RoomBulkCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rooms: List[RoomResponse]


class RoomTypeCreate(BaseModel):
    room_type_name: str = Field(
        ..., min_length=1, max_length=100, examples=["Deluxe King"]
    )


class RoomTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: Optional[uuid.UUID]
    room_type_name: str
    is_default: bool


class BedTypeCreate(BaseModel):
    bed_name: str = Field(
        ..., min_length=1, max_length=100, examples=["King", "Queen", "Twin"]
    )


class BedTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: Optional[uuid.UUID]
    bed_name: str
    is_default: bool


class AvailableRoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    room_name: str
    room_type: str
    bed_type: str
    base_rate: Decimal
    photos: RoomPhotos
    max_adults: int
    max_children: int
    status: RoomStatus
    floor_number: int
    cancellation_policy: CancellationPolicy
    cancellation_title: Optional[str]
    cancellation_description: Optional[str]
    system_amenities: List[AmenityResponse]
    custom_amenities: List[CustomAmenity]

    @field_validator("room_type", mode="before")
    @classmethod
    def extract_room_type_name(cls, v):
        if isinstance(v, str):
            return v
        # ORM relationship object — pull the name attribute
        return getattr(v, "room_type_name", None) or str(v)

    @field_validator("bed_type", mode="before")
    @classmethod
    def extract_bed_type_name(cls, v):
        if isinstance(v, str):
            return v
        # ORM relationship object — pull the name attribute
        return getattr(v, "bed_name", None) or str(v)
