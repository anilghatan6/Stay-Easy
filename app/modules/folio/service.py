import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.folio.repository import FolioRepository
from app.modules.booking.models.booking_model import (
    Booking,
    MasterBookingStatus,
)
from app.modules.auth.models.users_model import User
from app.modules.staff_mgmt.models.staffs_model import Staff, StaffProperty
from app.utils.exceptions import (
    BookingException,
    PermissionException,
    ServiceException,
)
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class FolioService:
    def __init__(
        self,
        db: AsyncSession,
        folio_repo: FolioRepository,
    ):
        self.db = db
        self.folio_repo = folio_repo

    # ─────────────────────── HELPERS ─────────────────────────

    async def _verify_staff_property_access(
        self, staff_user: User, property_id: uuid.UUID
    ) -> None:
        """Verify staff has access to the property."""
        if staff_user.role == "admin":
            return

        try:
            result = await self.db.execute(
                select(Staff).where(Staff.email == staff_user.email)
            )
            staff_record = result.scalar_one_or_none()
            if staff_record is None:
                raise PermissionException("Staff record not found for this user")

            result = await self.db.execute(
                select(StaffProperty).where(
                    StaffProperty.staff_id == staff_record.id,
                    StaffProperty.property_id == property_id,
                )
            )
            assigned = result.scalar_one_or_none()
            if not assigned:
                raise PermissionException("You are not assigned to this property")
        except PermissionException:
            raise
        except Exception as e:
            raise PermissionException("Could not verify staff assignment.")

    async def _resolve_staff_name(self, staff_user: User) -> str:
        """Resolve staff display name from the User object."""
        staff_name = await self.folio_repo.get_staff_name_by_id(staff_user.id)
        return staff_name or staff_user.full_name or staff_user.email

    def _recalculate_folio_totals(self, folio) -> tuple[Decimal, Decimal]:
        """Recalculate subtotal and total from charges + tax - discount."""
        subtotal = sum(charge.amount for charge in folio.charges)
        total = subtotal + folio.tax - folio.discount
        if total < Decimal("0.00"):
            total = Decimal("0.00")
        return subtotal, total

    def _get_booking_prop_id(self, booking) -> uuid.UUID:
        """Extract property_id from a Booking object."""
        return booking.property_id

    # ─────────────────────── FOLIO CRUD ─────────────────────────

    async def create_folio(
        self,
        property_id: uuid.UUID,
        ref_number: str,
        staff_user: User,
        tax: Decimal = Decimal("0.00"),
        discount: Decimal = Decimal("0.00"),
    ) -> dict:
        logger.info(f"[FolioService] Creating folio for booking {ref_number}")
        try:
            await self._verify_staff_property_access(staff_user, property_id)

            # Fetch booking
            from sqlalchemy import select
            result = await self.db.execute(
                select(Booking).where(Booking.ref_number == ref_number)
            )
            booking = result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Booking not found")

            if booking.property_id != property_id:
                raise BookingException("Booking does not belong to this property")

            # Only CHECKED_IN or CHECKED_OUT bookings can have folios
            if booking.status not in (
                MasterBookingStatus.CHECKED_IN,
                MasterBookingStatus.CHECKED_OUT,
            ):
                raise BookingException(
                    f"Cannot create folio for booking in status {booking.status}. "
                    "Guest must be checked in first."
                )

            # Check if folio already exists
            existing = await self.folio_repo.get_folio_by_booking_id(booking.id)
            if existing:
                raise BookingException("A folio already exists for this booking.")

            # Determine guest_id — use booking.guest_id (from guests table)
            guest_id = booking.guest_id
            if guest_id is None:
                raise BookingException(
                    "Booking has no linked guest. Cannot create folio."
                )

            folio = await self.folio_repo.create_folio(
                booking_id=booking.id,
                guest_id=guest_id,
                tax=tax,
                discount=discount,
            )

            # Auto-add room charges based on booked rooms and nights
            from sqlalchemy.orm import selectinload
            result = await self.db.execute(
                select(Booking)
                .where(Booking.id == booking.id)
                .options(selectinload(Booking.booking_rooms))
            )
            booking_with_rooms = result.scalar_one()

            nights = (booking.checkout_date - booking.checkin_date).days
            for br in booking_with_rooms.booking_rooms:
                # Fetch room base_rate
                from app.modules.pms.models.rooms_model import Rooms
                room_result = await self.db.execute(
                    select(Rooms).where(Rooms.id == br.room_unit_id)
                )
                room = room_result.scalar_one_or_none()
                if room:
                    room_total = room.base_rate * nights
                    await self.folio_repo.add_charge(
                        folio_id=folio.id,
                        description=f"Room charge: {room.room_name} ({nights} nights)",
                        amount=room_total,
                        category="ROOM_CHARGE",
                        posted_by=staff_user.id,
                    )

            await self.db.flush()

            # Recalculate totals after auto-charges
            folio = await self.folio_repo.get_folio_by_id(folio.id)
            subtotal, total = self._recalculate_folio_totals(folio)
            await self.folio_repo.update_folio_totals(folio.id, subtotal, total)

            await self.db.commit()

            # Reload with charges for response
            folio = await self.folio_repo.get_folio_by_id(folio.id)

            staff_name = await self._resolve_staff_name(staff_user)
            charges_response = [
                {
                    "id": c.id,
                    "folio_id": c.folio_id,
                    "description": c.description,
                    "amount": float(c.amount),
                    "category": c.category,
                    "posted_by": c.posted_by,
                    "posted_by_name": staff_name if c.posted_by == staff_user.id else await self.folio_repo.get_staff_name_by_id(c.posted_by),
                    "posted_at": c.posted_at,
                }
                for c in folio.charges
            ]

            return {
                "id": folio.id,
                "booking_id": folio.booking_id,
                "guest_id": folio.guest_id,
                "status": folio.status.value,
                "subtotal": float(folio.subtotal),
                "tax": float(folio.tax),
                "discount": float(folio.discount),
                "total": float(folio.total),
                "settled_at": folio.settled_at,
                "charges_count": len(folio.charges),
                "charges": charges_response,
                "created_at": folio.created_at,
                "updated_at": folio.updated_at,
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[FolioService] Error creating folio: {e}")
            raise ServiceException("Could not create folio. Please try again.")

    async def get_folio(
        self,
        folio_id: uuid.UUID,
        staff_user: User,
    ) -> dict:
        logger.info(f"[FolioService] Getting folio {folio_id}")
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            # Verify staff access via booking's property
            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            # Resolve all staff names for charges
            charges_response = []
            for c in folio.charges:
                staff_name = await self.folio_repo.get_staff_name_by_id(c.posted_by)
                charges_response.append({
                    "id": c.id,
                    "folio_id": c.folio_id,
                    "description": c.description,
                    "amount": float(c.amount),
                    "category": c.category,
                    "posted_by": c.posted_by,
                    "posted_by_name": staff_name,
                    "posted_at": c.posted_at,
                })

            return {
                "id": folio.id,
                "booking_id": folio.booking_id,
                "guest_id": folio.guest_id,
                "status": folio.status.value,
                "subtotal": float(folio.subtotal),
                "tax": float(folio.tax),
                "discount": float(folio.discount),
                "total": float(folio.total),
                "settled_at": folio.settled_at,
                "charges": charges_response,
                "created_at": folio.created_at,
                "updated_at": folio.updated_at,
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            logger.error(f"[FolioService] Error getting folio: {e}")
            raise ServiceException("Could not fetch folio.")

    async def list_folios_by_property(
        self,
        property_id: uuid.UUID,
        staff_user: User,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        logger.info(f"[FolioService] Listing folios for property {property_id}")
        try:
            await self._verify_staff_property_access(staff_user, property_id)

            folios, total = await self.folio_repo.get_folios_by_property(
                property_id, skip, limit
            )

            folios_data = []
            for folio in folios:
                folios_data.append({
                    "id": folio.id,
                    "booking_id": folio.booking_id,
                    "guest_id": folio.guest_id,
                    "status": folio.status.value,
                    "subtotal": float(folio.subtotal),
                    "tax": float(folio.tax),
                    "discount": float(folio.discount),
                    "total": float(folio.total),
                    "settled_at": folio.settled_at,
                    "charges_count": len(folio.charges),
                    "created_at": folio.created_at,
                    "updated_at": folio.updated_at,
                })

            has_more = skip + len(folios) < total

            return {
                "folios": folios_data,
                "total": total,
                "skip": skip,
                "limit": limit,
                "has_more": has_more,
            }

        except PermissionException:
            raise
        except Exception as e:
            logger.error(f"[FolioService] Error listing folios: {e}")
            raise ServiceException("Could not fetch folios.")

    async def update_folio(
        self,
        folio_id: uuid.UUID,
        staff_user: User,
        tax: Optional[Decimal] = None,
        discount: Optional[Decimal] = None,
    ) -> dict:
        logger.info(f"[FolioService] Updating folio {folio_id}")
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            if folio.status.value not in ("OPEN", "PARTIALLY_PAID"):
                raise BookingException(
                    f"Cannot update folio in status {folio.status.value}"
                )

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            new_tax = tax if tax is not None else folio.tax
            new_discount = discount if discount is not None else folio.discount

            await self.folio_repo.update_folio_tax_discount(
                folio_id, new_tax, new_discount
            )

            # Recalculate totals
            subtotal, total = self._recalculate_folio_totals(folio)
            # Override with new tax/discount for total calc
            total = subtotal + new_tax - new_discount
            if total < Decimal("0.00"):
                total = Decimal("0.00")
            await self.folio_repo.update_folio_totals(folio_id, subtotal, total)

            await self.db.commit()

            folio = await self.folio_repo.get_folio_by_id(folio_id)

            return {
                "id": folio.id,
                "status": folio.status.value,
                "subtotal": float(folio.subtotal),
                "tax": float(folio.tax),
                "discount": float(folio.discount),
                "total": float(folio.total),
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[FolioService] Error updating folio: {e}")
            raise ServiceException("Could not update folio.")

    async def settle_folio(
        self,
        folio_id: uuid.UUID,
        staff_user: User,
    ) -> dict:
        logger.info(f"[FolioService] Settling folio {folio_id}")
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            if folio.status.value not in ("OPEN", "PARTIALLY_PAID"):
                raise BookingException(
                    f"Cannot settle folio in status {folio.status.value}"
                )

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            await self.folio_repo.settle_folio(folio_id)
            await self.db.commit()

            folio = await self.folio_repo.get_folio_by_id(folio_id)

            return {
                "id": folio.id,
                "status": folio.status.value,
                "total": float(folio.total),
                "settled_at": folio.settled_at,
                "message": "Folio settled successfully.",
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[FolioService] Error settling folio: {e}")
            raise ServiceException("Could not settle folio.")

    async def waive_folio(
        self,
        folio_id: uuid.UUID,
        staff_user: User,
    ) -> dict:
        logger.info(f"[FolioService] Waiving folio {folio_id}")
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            if folio.status.value not in ("OPEN", "PARTIALLY_PAID"):
                raise BookingException(
                    f"Cannot waive folio in status {folio.status.value}"
                )

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            await self.folio_repo.waive_folio(folio_id)
            await self.db.commit()

            folio = await self.folio_repo.get_folio_by_id(folio_id)

            return {
                "id": folio.id,
                "status": folio.status.value,
                "total": float(folio.total),
                "settled_at": folio.settled_at,
                "message": "Folio waived successfully.",
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[FolioService] Error waiving folio: {e}")
            raise ServiceException("Could not waive folio.")

    # ─────────────────────── CHARGE CRUD ─────────────────────────

    async def add_charge(
        self,
        folio_id: uuid.UUID,
        staff_user: User,
        description: str,
        amount: Decimal,
        category: str,
    ) -> dict:
        logger.info(f"[FolioService] Adding charge to folio {folio_id}")
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            if folio.status.value not in ("OPEN", "PARTIALLY_PAID"):
                raise BookingException(
                    f"Cannot add charge to folio in status {folio.status.value}"
                )

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            if amount <= Decimal("0.00"):
                raise BookingException("Charge amount must be positive.")

            charge = await self.folio_repo.add_charge(
                folio_id=folio_id,
                description=description,
                amount=amount,
                category=category,
                posted_by=staff_user.id,
            )

            # Recalculate totals
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            subtotal, total = self._recalculate_folio_totals(folio)
            await self.folio_repo.update_folio_totals(folio_id, subtotal, total)

            # Update folio status based on total
            new_status = "OPEN"
            if total > Decimal("0.00") and folio.status.value == "OPEN":
                new_status = "PARTIALLY_PAID"
            await self.db.execute(
                update(Folio).where(Folio.id == folio_id).values(status=new_status)
            )

            await self.db.commit()

            staff_name = await self._resolve_staff_name(staff_user)

            return {
                "id": charge.id,
                "folio_id": charge.folio_id,
                "description": charge.description,
                "amount": float(charge.amount),
                "category": charge.category,
                "posted_by": charge.posted_by,
                "posted_by_name": staff_name,
                "posted_at": charge.posted_at,
                "folio_subtotal": float(subtotal),
                "folio_total": float(total),
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[FolioService] Error adding charge: {e}")
            raise ServiceException("Could not add charge.")

    async def list_charges(
        self,
        folio_id: uuid.UUID,
        staff_user: User,
    ) -> list[dict]:
        logger.info(f"[FolioService] Listing charges for folio {folio_id}")
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            charges = await self.folio_repo.get_charges_by_folio_id(folio_id)

            charges_response = []
            for c in charges:
                staff_name = await self.folio_repo.get_staff_name_by_id(c.posted_by)
                charges_response.append({
                    "id": c.id,
                    "folio_id": c.folio_id,
                    "description": c.description,
                    "amount": float(c.amount),
                    "category": c.category,
                    "posted_by": c.posted_by,
                    "posted_by_name": staff_name,
                    "posted_at": c.posted_at,
                })

            return charges_response

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            logger.error(f"[FolioService] Error listing charges: {e}")
            raise ServiceException("Could not fetch charges.")

    async def update_charge(
        self,
        folio_id: uuid.UUID,
        charge_id: uuid.UUID,
        staff_user: User,
        description: Optional[str] = None,
        amount: Optional[Decimal] = None,
        category: Optional[str] = None,
    ) -> dict:
        logger.info(f"[FolioService] Updating charge {charge_id}")
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            if folio.status.value not in ("OPEN", "PARTIALLY_PAID"):
                raise BookingException(
                    f"Cannot update charge on folio in status {folio.status.value}"
                )

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            charge = await self.folio_repo.get_charge_by_id(folio_id, charge_id)
            if charge is None:
                raise BookingException("Charge not found.")

            if amount is not None and amount <= Decimal("0.00"):
                raise BookingException("Charge amount must be positive.")

            await self.folio_repo.update_charge(
                charge_id=charge_id,
                description=description,
                amount=amount,
                category=category,
            )

            # Recalculate totals
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            subtotal, total = self._recalculate_folio_totals(folio)
            await self.folio_repo.update_folio_totals(folio_id, subtotal, total)

            await self.db.commit()

            # Fetch updated charge
            updated_charge = await self.folio_repo.get_charge_by_id(folio_id, charge_id)
            staff_name = await self.folio_repo.get_staff_name_by_id(updated_charge.posted_by)

            return {
                "id": updated_charge.id,
                "folio_id": updated_charge.folio_id,
                "description": updated_charge.description,
                "amount": float(updated_charge.amount),
                "category": updated_charge.category,
                "posted_by": updated_charge.posted_by,
                "posted_by_name": staff_name,
                "posted_at": updated_charge.posted_at,
                "folio_subtotal": float(subtotal),
                "folio_total": float(total),
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[FolioService] Error updating charge: {e}")
            raise ServiceException("Could not update charge.")

    async def delete_charge(
        self,
        folio_id: uuid.UUID,
        charge_id: uuid.UUID,
        staff_user: User,
    ) -> dict:
        logger.info(f"[FolioService] Deleting charge {charge_id}")
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            if folio.status.value not in ("OPEN", "PARTIALLY_PAID"):
                raise BookingException(
                    f"Cannot delete charge on folio in status {folio.status.value}"
                )

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            deleted = await self.folio_repo.delete_charge(folio_id, charge_id)
            if not deleted:
                raise BookingException("Charge not found.")

            # Recalculate totals
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            subtotal, total = self._recalculate_folio_totals(folio)
            await self.folio_repo.update_folio_totals(folio_id, subtotal, total)

            await self.db.commit()

            return {
                "folio_id": folio_id,
                "deleted_charge_id": charge_id,
                "folio_subtotal": float(subtotal),
                "folio_total": float(total),
                "message": "Charge deleted successfully.",
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[FolioService] Error deleting charge: {e}")
            raise ServiceException("Could not delete charge.")
