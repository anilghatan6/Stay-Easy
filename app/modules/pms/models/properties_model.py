import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, ForeignKey, Integer, Boolean, Numeric, 
    UniqueConstraint, Index, CheckConstraint, Enum as SqlEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import StrEnum
from app.utils.timestamp import TimestampMixin
from app.config.database_config import Base
from app.modules.pms.models.nested_mutable import NestedMutable

class PropertyType(StrEnum):
    HOTEL = "HOTEL"
    HOSTEL = "HOSTEL"
    VILLA = "VILLA"
    APARTMENT = "APARTMENT"
    RESORT = "RESORT"
    GUESTHOUSE = "GUESTHOUSE"
    RESTURANT = "RESTURANT"
    OTHER = "OTHER"


class Property(Base, TimestampMixin):
    __tablename__ = "properties"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_property_name"),
        Index("ix_properties_geo_location", "country", "state", "city","address"),
        CheckConstraint(
            "check_in_grace_period >= 0",
            name="chk_check_in_grace_period_non_negative",
        ),
        CheckConstraint(
            "check_out_grace_period >= 0",
            name="chk_check_out_grace_period_non_negative",
        ),
        CheckConstraint(
            "number_of_floors >= 1",
            name="chk_min_floors",
        ),
        CheckConstraint(
            "total_rooms >= 1",
            name="chk_total_rooms_non_negative",
        ),
        CheckConstraint(
            "year_built >= 1800 AND year_built <= 2100",
            name="chk_year_built_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[PropertyType] = mapped_column(
        SqlEnum(PropertyType, native_enum=False, length=20),
        nullable=False,
        default=PropertyType.HOTEL,
    )
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    country: Mapped[str] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str] = mapped_column(String(20), nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=9, scale=6), nullable=True
    )
    longitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=9, scale=6), nullable=True
    )

    check_in_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    check_out_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    check_in_grace_period: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, nullable=True
    )
    check_out_grace_period: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, nullable=True
    )
    always_allow_check_in_out :Mapped[bool] = mapped_column(Boolean, default=False)
    number_of_floors: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    total_rooms: Mapped[int] = mapped_column(Integer, default=1, nullable=True)
    year_built: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", nullable=True)
    language: Mapped[str] = mapped_column(String(100), nullable=True)
   
    brand_logo_url:Mapped[str] = mapped_column(String(2048), nullable=True)
    brand_color:Mapped[str] = mapped_column(String(20), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    system_amenity_ids: Mapped[List[uuid.UUID]] = mapped_column(
        MutableList.as_mutable(ARRAY(UUID(as_uuid=True))), server_default="{}", nullable=True
    )
    custom_amenities: Mapped[List[Dict[str, Any]]] = mapped_column(
        NestedMutable.as_mutable(JSONB), server_default="[]", nullable=True
    )

    photos: Mapped[Dict[str, Any]] = mapped_column(
        NestedMutable.as_mutable(JSONB), 
        server_default='{"cover": null, "gallery": []}', 
        nullable=True
    )

    # ─── GENERAL RELATIONSHIPS ──────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="properties")
    rooms:Mapped[List["Rooms"]] = relationship("Rooms",back_populates="property",cascade="all,delete-orphan",passive_deletes=True,)
    bed_types:Mapped[List["BedType"]] = relationship("BedType",back_populates="property",cascade="all,delete-orphan",passive_deletes=True,)
    room_types:Mapped[List["RoomType"]] = relationship("RoomType",back_populates="property",cascade="all,delete-orphan",passive_deletes=True,)
    
    special_offers: Mapped[List["SpecialOffer"]] = relationship(
        "SpecialOffer", back_populates="property", cascade="all, delete-orphan", passive_deletes=True
    )


class Amenity(Base, TimestampMixin):
    __tablename__ = "amenities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon:Mapped[str] = mapped_column(String(100), nullable=True)


