from pydantic import field_validator
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.pms.models.rooms_model import CancellationPolicy, RoomStatus

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
 
    cover:str = Field(default=None)
    gallery: List[str] = Field(default_factory=list)
 
    @field_validator("gallery")
    @classmethod
    def limit_gallery_size(cls, v: List[str]) -> List[str]:
        # UI caps at 5 total photos (cover + gallery combined)
        if len(v) > 4:
            raise ValueError("A room can have at most 5 photos total (1 cover + 4 gallery).")
        return v

class CustomAmenity(BaseModel):
    """One inline custom amenity entry, e.g. from the 'Add a custom amenity' input."""
 
    name: str = Field(..., min_length=1, max_length=100)
    icon: Optional[str] = None  
 
class RoomBase(BaseModel):
    floor_number: int = Field(..., ge=0, le=100, description="Floor number (0 = ground floor)")
    room_name: str = Field(..., min_length=1, max_length=100, examples=["Ocean Suite A"])
    room_type_id: uuid.UUID
    bed_type_id: uuid.UUID
 
    photos: RoomPhotos = Field(default_factory=RoomPhotos)
 
    max_adults: int = Field(2, ge=1, le=30)
    max_children: int = Field(0, ge=0, le=15)
 
    # RATES & POLICIES
    base_rate: Decimal = Field(
        ..., ge=1, decimal_places=2, description="Minimum rate per night (USD)"
    )
    status: RoomStatus = Field(RoomStatus.AVAILABLE, nullable=False)
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
    rooms:List[RoomBase] = Field (...,min_length=1, max_length=50,description="List of rooms to be created")

    @model_validator(mode="after")
    def no_duplicate_room_names_within_batch(self) -> "RoomBulkCreateRequest":
        names = [r.room_name.strip().lower() for r in self.rooms]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(
                f"Duplicate room name within this request: {', '.join(sorted(dupes))}"
            )
        return self
 
class RoomResponse(RoomBase):
    model_config = ConfigDict(from_attributes=True)
 
    id: uuid.UUID
    property_id: uuid.UUID

class RoomBulkCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rooms: List[RoomResponse]


class RoomTypeCreate(BaseModel):
    room_type_name: str = Field(..., min_length=1, max_length=100, examples=["Deluxe King"])
 
class RoomTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
 
    id: uuid.UUID
    property_id: Optional[uuid.UUID]
    room_type_name: str
    is_default: bool


class BedTypeCreate(BaseModel):
    bed_name: str = Field(..., min_length=1, max_length=100, examples=["King", "Queen", "Twin"])

class BedTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
 
    id: uuid.UUID
    property_id: Optional[uuid.UUID]
    bed_name: str
    is_default: bool


# class RoomTypeBase(BaseModel):
#     room_type_name: str = Field(
#         ...,
#         title="Room Type Name",
#         description="Name of the room type",
#         examples=["Standard", "Deluxe", "Suite", "Twin", "Double", "Single"],
#         min_length=2,
#         max_length=100,
#     )
#     is_default: bool = Field(
#         default=False,
#         description="Indicates if the room type is a default type or custom",
#     )
#     model_config = ConfigDict(from_attributes=True)


# class RoomTypeResponse(RoomTypeBase, TimestampSchema):
#     id: uuid.UUID
#     hotel_detail_id: Optional[uuid.UUID] = None
#     model_config = ConfigDict(from_attributes=True)


# class BedTypeBase(BaseModel):
#     bed_name: str = Field(
#         ...,
#         title="Bed Type Name",
#         description="Name of the bed type",
#         examples=["King", "Queen", "Twin", "Double", "Single"],
#         min_length=2,
#         max_length=100,
#     )
#     is_default: bool = Field(
#         default=False,
#         description="Indicates if the bed type is a default type or custom",
#     )
#     model_config = ConfigDict(from_attributes=True)


# class BedTypeResponse(BedTypeBase, TimestampSchema):
#     id: uuid.UUID
#     hotel_detail_id: Optional[uuid.UUID] = None
#     model_config = ConfigDict(from_attributes=True)


# class RoomsBase(BaseModel):
#     room_name: str = Field(
#         ...,
#         title="Room Name",
#         description="Unique identifier or number for this specific room record",
#         examples=["101", "102", "Deluxe Suite A"],
#         min_length=1,
#         max_length=50,
#     )
#     floor_number: int = Field(
#         ...,
#         title="Floor Number",
#         description="Floor number or identifier",
#         ge=0,
#         le=100,
#     )
#     max_adults: int = Field(
#         ...,
#         title="Maximum Number of Adults",
#         description="Maximum number of adults allowed in the room",
#         ge=1,
#         le=30,
#     )
#     max_children: int = Field(
#         ...,
#         title="Maximum Number of Children",
#         description="Maximum number of children allowed in the room",
#         ge=0,
#         le=15,
#     )
#     base_rate: Decimal = Field(
#         ...,
#         title="Base Rate",
#         description="Base rate for the room per night",
#         ge=0,
#         le=100000,
#     )
#     status: RoomStatus = Field(
#         RoomStatus.AVAILABLE,
#         title="Status",
#         description="Current status of the room (e.g. AVAILABLE, DIRTY, OCCUPIED)",
#         examples=["AVAILABLE", "DIRTY", "OCCUPIED"],
#     )
#     cancellation_policy: CancellationPolicy = Field(
#         CancellationPolicy.FLEXIBLE,
#         title="Cancellation Policy",
#         description="Cancellation policy for the room (e.g. FLEXIBLE, STRICT)",
#         examples=["FLEXIBLE", "STRICT"],
#     )
#     cancellation_notes: Optional[str] = Field(
#         None,
#         title="Cancellation Notes",
#         description="Additional notes regarding the cancellation policy",
#         examples=["Cancellation is free up to 24 hours before check-in"],
#     )
#     room_type: RoomTypeBase = Field(
#         ..., description="Room type characteristics associated with this room"
#     )
#     bed_type: BedTypeBase = Field(
#         ..., description="Bed configuration profile associated with this room"
#     )
#     photos: List[str] = Field(
#         default_factory=list,
#         description="List of raw photo string URLs associated with the room",
#     )
#     amenities: List[uuid.UUID] = Field(
#         default_factory=list,
#         description="List of Amenity model UUID keys attached to this room",
#     )

#     # it must be greater than 0 and between 1 to 100000 base rate only
#     @field_validator("base_rate", mode="before")
#     @classmethod
#     def validate_base_rate(cls, value: any) -> Decimal:
#         try:
#             value = Decimal(value)
#             if value <= 0 or value > 100000:
#                 raise ValueError(
#                     "must be greater than 0 and between 1 to 100000"
#                 )
#             return value
#         except ValueError:
#             raise
#         except Exception:
#             raise ValueError("Base rate must be a valid number")

#     @field_validator("photos")
#     @classmethod
#     def validate_photo_urls(cls, v: List[str]) -> List[str]:
#         """Validate photo urls and raise error on duplicates."""
#         if not v:
#             return []

#         if len(v) > MAX_IMAGE_PER_ROOM:
#             raise ValueError(
#                 f"Exceeded maximum number of images allowed: {MAX_IMAGE_PER_ROOM}"
#             )

#         seen = set()
#         unique_photo_urls = []
#         duplicates = []

#         for photo_url in v:
#             # Strip whitespace
#             clean_photo_url = photo_url.strip()

#             # Skip empty strings
#             if not clean_photo_url:
#                 continue

#             # Case-insensitive check
#             normalized = clean_photo_url.lower()

#             if normalized not in seen:
#                 seen.add(normalized)
#                 unique_photo_urls.append(photo_url)
#             else:
#                 duplicates.append(photo_url)

#         if duplicates:
#             raise ValueError(
#                 f"Duplicate photo urls found: {', '.join(set([a.photo_url for a in duplicates]))}. "
#                 f"Please remove duplicates before submitting."
#             )

#         return unique_photo_urls

# class RoomsCreate(BaseModel):
#     rooms: List[RoomsBase] = Field(..., min_length=1)

# class RoomsUpdate(BaseModel):
#     room_name: Optional[str] = Field(
#         ...,
#         title="Room Name",
#         description="Unique identifier or number for this specific room record",
#         examples=["101", "102", "Deluxe Suite A"],
#         min_length=1,
#         max_length=50,
#     )
#     floor_number: Optional[int] = Field(
#         ...,
#         title="Floor Number",
#         description="Floor number or identifier",
#         ge=0,
#         le=100,
#     )
#     max_adults: Optional[int] = Field(
#         ...,
#         title="Maximum Number of Adults",
#         description="Maximum number of adults allowed in the room",
#         ge=1,
#         le=30,
#     )
#     max_children: Optional[int] = Field(
#         ...,
#         title="Maximum Number of Children",
#         description="Maximum number of children allowed in the room",
#         ge=0,
#         le=15,
#     )
#     base_rate: Optional[Decimal] = Field(
#         ...,
#         title="Base Rate",
#         description="Base rate for the room per night",
#         ge=0,
#         le=100000,
#     )
#     status: Optional[RoomStatus] = Field(
#         RoomStatus.AVAILABLE,
#         title="Status",
#         description="Current status of the room (e.g. AVAILABLE, DIRTY, OCCUPIED)",
#         examples=["AVAILABLE", "DIRTY", "OCCUPIED"],
#     )
#     cancellation_policy: Optional[CancellationPolicy] = Field(
#         CancellationPolicy.FLEXIBLE,
#         title="Cancellation Policy",
#         description="Cancellation policy for the room (e.g. FLEXIBLE, STRICT)",
#         examples=["FLEXIBLE", "STRICT"],
#     )
#     cancellation_notes: Optional[str] = Field(
#         None,
#         title="Cancellation Notes",
#         description="Additional notes regarding the cancellation policy",
#         examples=["Cancellation is free up to 24 hours before check-in"],
#     )
#     room_type: Optional[RoomTypeBase] = Field(
#         ..., description="Room type characteristics associated with this room"
#     )
#     bed_type: Optional[BedTypeBase] = Field(
#         ..., description="Bed configuration profile associated with this room"
#     )
#     photos: Optional[List[str]] = Field(
#         default_factory=list,
#         description="List of raw photo string URLs associated with the room",
#     )
#     amenities: Optional[List[uuid.UUID]] = Field(
#         default_factory=list,
#         description="List of Amenity model UUID keys attached to this room",
#     )

#     @field_validator("photos")
#     @classmethod
#     def validate_photo_urls(cls, v: List[str]) -> List[str]:
#         """Validate photo urls and raise error on duplicates."""
#         if not v:
#             return []

#         if len(v) > MAX_IMAGE_PER_ROOM:
#             raise ValueError(
#                 f"Exceeded maximum number of images allowed: {MAX_IMAGE_PER_ROOM}"
#             )

#         seen = set()
#         unique_photo_urls = []
#         duplicates = []

#         for photo_url in v:
#             # Strip whitespace
#             clean_photo_url = photo_url.strip()

#             # Skip empty strings
#             if not clean_photo_url:
#                 continue

#             # Case-insensitive check
#             normalized = clean_photo_url.lower()

#             if normalized not in seen:
#                 seen.add(normalized)
#                 unique_photo_urls.append(photo_url)
#             else:
#                 duplicates.append(photo_url)

#         if duplicates:
#             raise ValueError(
#                 f"Duplicate photo urls found: {', '.join(set([a.photo_url for a in duplicates]))}. "
#                 f"Please remove duplicates before submitting."
#             )

#         return unique_photo_urls


# class RoomsResponse(BaseModel):
#     id: uuid.UUID
#     room: RoomsBase
#     model_config = ConfigDict(from_attributes=True)


# class AmenityDetailResponse(BaseModel):
#     id: uuid.UUID
#     name: str
#     is_default: bool
    
#     model_config = ConfigDict(from_attributes=True)



# class RoomsDetailResponse(BaseModel):
#     id: uuid.UUID
#     room_name: str 
#     floor_number: int 
#     max_adults: int 
#     max_children: int 
#     base_rate: Decimal
#     status: str
#     cancellation_policy: str
#     cancellation_notes: Optional[str]
#     room_type: RoomTypeBase
#     bed_type: BedTypeBase
#     photos: List[str]
#     amenities: List[AmenityDetailResponse]
#     model_config = ConfigDict(from_attributes=True)


