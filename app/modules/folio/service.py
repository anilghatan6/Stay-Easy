import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.users_model import User
from app.modules.booking.models.booking_model import (
    Booking,
    MasterBookingStatus,
    PaymentGateway,
    PaymentStatus,
)
from app.modules.booking.models.folio_models import Folio
from app.modules.folio.repository import FolioRepository
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
        """Recalculate subtotal and total from charges with percentage-based tax/discount."""
        subtotal = sum(charge.amount for charge in folio.charges)
        tax_amount = subtotal * (folio.tax / Decimal("100"))
        discount_amount = subtotal * (folio.discount / Decimal("100"))
        total = subtotal + tax_amount - discount_amount
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

            # Only CHECKED_IN bookings can have folios
            if booking.status not in (MasterBookingStatus.CHECKED_IN):
                raise BookingException(
                    f"Cannot create folio for booking in status {booking.status}. "
                    "Guest must be checked in first."
                )

            # Check if folio already exists
            existing = await self.folio_repo.get_folio_by_booking_id(booking.id)
            if existing:
                raise BookingException("A folio already exists for this booking.")

            folio = await self.folio_repo.create_folio(
                booking_id=booking.id,
                guest_id=booking.guest_id,
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
                    "posted_by_name": staff_name
                    if c.posted_by == staff_user.id
                    else await self.folio_repo.get_staff_name_by_id(c.posted_by),
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
                charges_response.append(
                    {
                        "id": c.id,
                        "folio_id": c.folio_id,
                        "description": c.description,
                        "amount": float(c.amount),
                        "category": c.category,
                        "posted_by": c.posted_by,
                        "posted_by_name": staff_name,
                        "posted_at": c.posted_at,
                    }
                )

            # Recalculate from charges to ensure accuracy
            subtotal = (
                sum(c.amount for c in folio.charges)
                if folio.charges
                else Decimal("0.00")
            )
            tax_amount = subtotal * (folio.tax / Decimal("100"))
            discount_amount = subtotal * (folio.discount / Decimal("100"))
            total = subtotal + tax_amount - discount_amount
            if total < Decimal("0.00"):
                total = Decimal("0.00")

            remaining_balance = total - booking.amount_paid
            if remaining_balance < Decimal("0.00"):
                remaining_balance = Decimal("0.00")

            return {
                "id": folio.id,
                "booking_id": folio.booking_id,
                "guest_id": folio.guest_id,
                "status": folio.status.value,
                "subtotal": float(subtotal),
                "tax": float(folio.tax),
                "discount": float(folio.discount),
                "total": float(total),
                "amount_paid": float(booking.amount_paid),
                "remaining_balance": float(remaining_balance),
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
                guest_name = None
                guest_email = None
                amount_paid = 0.0
                if folio.booking:
                    if folio.booking.guest:
                        guest_name = folio.booking.guest.full_name
                        guest_email = folio.booking.guest.email
                    elif folio.booking.booking_guest:
                        guest_name = folio.booking.booking_guest.full_name
                        guest_email = folio.booking.booking_guest.email
                    amount_paid = float(folio.booking.amount_paid)

                # Recalculate from charges to ensure accuracy
                subtotal = (
                    sum(c.amount for c in folio.charges)
                    if folio.charges
                    else Decimal("0.00")
                )
                tax_amount = subtotal * (folio.tax / Decimal("100"))
                discount_amount = subtotal * (folio.discount / Decimal("100"))
                folio_total = subtotal + tax_amount - discount_amount
                if folio_total < Decimal("0.00"):
                    folio_total = Decimal("0.00")

                remaining_balance = folio_total - Decimal(str(amount_paid))
                if remaining_balance < Decimal("0.00"):
                    remaining_balance = Decimal("0.00")

                folios_data.append(
                    {
                        "id": folio.id,
                        "booking_id": folio.booking_id,
                        "guest_id": folio.guest_id,
                        "guest_name": guest_name,
                        "guest_email": guest_email,
                        "status": folio.status.value,
                        "subtotal": float(subtotal),
                        "tax": float(folio.tax),
                        "discount": float(folio.discount),
                        "total": float(folio_total),
                        "amount_paid": amount_paid,
                        "remaining_balance": float(remaining_balance),
                        "settled_at": folio.settled_at,
                        "charges_count": len(folio.charges),
                        "created_at": folio.created_at,
                        "updated_at": folio.updated_at,
                    }
                )

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

            # Recalculate subtotal from charges, apply new tax/discount percentages
            subtotal = sum(charge.amount for charge in folio.charges)
            tax_amount = subtotal * (new_tax / Decimal("100"))
            discount_amount = subtotal * (new_discount / Decimal("100"))
            total = subtotal + tax_amount - discount_amount
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

    # ─────────────────────── FOLIO PAYMENTS ─────────────────────────

    async def pay_folio(
        self,
        folio_id: uuid.UUID,
        staff_user: User,
        amount: Decimal,
        payment_gateway: str,
    ) -> dict:
        """Record a payment against a folio, reducing the outstanding balance."""
        logger.info(
            f"[FolioService] Recording payment of {amount} for folio {folio_id}"
        )
        try:
            folio = await self.folio_repo.get_folio_by_id(folio_id)
            if folio is None:
                raise BookingException("Folio not found")

            if folio.status.value not in ("OPEN", "PARTIALLY_PAID"):
                raise BookingException(
                    f"Cannot accept payment for folio in status {folio.status.value}"
                )

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            await self._verify_staff_property_access(staff_user, booking.property_id)

            if amount <= Decimal("0.00"):
                raise BookingException("Payment amount must be positive.")

            # Recalculate folio total from charges (don't trust stale DB value)
            subtotal = (
                sum(c.amount for c in folio.charges)
                if folio.charges
                else Decimal("0.00")
            )
            tax_amount = subtotal * (folio.tax / Decimal("100"))
            discount_amount = subtotal * (folio.discount / Decimal("100"))
            total = subtotal + tax_amount - discount_amount
            if total < Decimal("0.00"):
                total = Decimal("0.00")

            # Update folio totals in DB to stay in sync
            await self.folio_repo.update_folio_totals(folio_id, subtotal, total)

            # Outstanding = folio total minus what guest already paid
            outstanding = total - booking.amount_paid
            if outstanding < Decimal("0.00"):
                outstanding = Decimal("0.00")

            if amount > outstanding:
                raise BookingException(
                    f"Payment amount ({float(amount):.2f}) exceeds outstanding balance ({float(outstanding):.2f}). "
                    f"Folio total: {float(total):.2f}, already paid: {float(booking.amount_paid):.2f}"
                )

            # Update booking payment tracking
            booking.amount_paid = booking.amount_paid + amount
            booking.amount_due = booking.total_amount - booking.amount_paid
            if booking.amount_due < Decimal("0.00"):
                booking.amount_due = Decimal("0.00")

            # Update payment status
            if booking.amount_due <= Decimal("0.00"):
                booking.payment_status = PaymentStatus.PAID
            elif booking.amount_paid > Decimal("0.00"):
                booking.payment_status = PaymentStatus.PARTIAL
            else:
                booking.payment_status = PaymentStatus.UNPAID

            if payment_gateway:
                booking.payment_gateway = (
                    PaymentGateway(payment_gateway.upper())
                    if isinstance(payment_gateway, str)
                    else payment_gateway
                )

            # If folio is fully paid, mark as PAID; otherwise PARTIALLY_PAID
            new_outstanding = total - booking.amount_paid
            if new_outstanding <= Decimal("0.00"):
                await self.folio_repo.settle_folio(folio_id)
            elif folio.status.value == "OPEN":
                await self.folio_repo.mark_partially_paid(folio_id)

            await self.db.commit()

            folio = await self.folio_repo.get_folio_by_id(folio_id)
            remaining_balance = total - booking.amount_paid

            return {
                "folio_id": folio.id,
                "folio_status": folio.status.value
                if hasattr(folio.status, "value")
                else folio.status,
                "folio_total": float(folio.total),
                "amount_paid": float(booking.amount_paid),
                "remaining_balance": float(remaining_balance),
                "payment_status": booking.payment_status.value
                if hasattr(booking.payment_status, "value")
                else booking.payment_status,
                "payment_gateway": booking.payment_gateway
                if isinstance(booking.payment_gateway, str)
                else booking.payment_gateway.value
                if booking.payment_gateway
                else None,
                "message": f"Payment of {float(amount):.2f} recorded successfully.",
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"[FolioService] Error recording payment for folio {folio_id}: {e}"
            )
            raise ServiceException("Could not record payment.")

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

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            if booking.status not in (MasterBookingStatus.CHECKED_IN):
                raise BookingException(
                    f"Cannot add charge to folio for booking in status {booking.status}. "
                    "Guest must be checked in first."
                )

            await self._verify_staff_property_access(staff_user, booking.property_id)

            if folio.status.value == "WAIVED":
                raise BookingException("Cannot add charges to a waived folio.")

            if amount <= Decimal("0.00"):
                raise BookingException("Charge amount must be positive.")

            # Calculate new totals before adding the charge
            old_subtotal = sum(c.amount for c in folio.charges)
            new_subtotal = old_subtotal + amount
            tax_amount = new_subtotal * (folio.tax / Decimal("100"))
            discount_amount = new_subtotal * (folio.discount / Decimal("100"))
            new_total = new_subtotal + tax_amount - discount_amount
            if new_total < Decimal("0.00"):
                new_total = Decimal("0.00")

            charge = await self.folio_repo.add_charge(
                folio_id=folio_id,
                description=description,
                amount=amount,
                category=category,
                posted_by=staff_user.id,
            )

            await self.folio_repo.update_folio_totals(folio_id, new_subtotal, new_total)

            if folio.status.value == "PAID":
                await self.folio_repo.mark_partially_paid(folio_id)

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
                "folio_subtotal": float(new_subtotal),
                "folio_total": float(new_total),
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
                charges_response.append(
                    {
                        "id": c.id,
                        "folio_id": c.folio_id,
                        "description": c.description,
                        "amount": float(c.amount),
                        "category": c.category,
                        "posted_by": c.posted_by,
                        "posted_by_name": staff_name,
                        "posted_at": c.posted_at,
                    }
                )

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

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            if booking.status not in (MasterBookingStatus.CHECKED_IN):
                raise BookingException(
                    f"Cannot update charge for booking in status {booking.status}. "
                    "Guest must be checked in first."
                )

            await self._verify_staff_property_access(staff_user, booking.property_id)

            if folio.status.value == "WAIVED":
                raise BookingException("Cannot update charges on a waived folio.")

            charge = await self.folio_repo.get_charge_by_id(folio_id, charge_id)
            if charge is None:
                raise BookingException("Charge not found.")

            if amount is not None and amount <= Decimal("0.00"):
                raise BookingException("Charge amount must be positive.")

            # Calculate new totals before updating the charge
            old_subtotal = sum(c.amount for c in folio.charges)
            new_charge_amount = amount if amount is not None else charge.amount
            new_subtotal = old_subtotal - charge.amount + new_charge_amount
            tax_amount = new_subtotal * (folio.tax / Decimal("100"))
            discount_amount = new_subtotal * (folio.discount / Decimal("100"))
            new_total = new_subtotal + tax_amount - discount_amount
            if new_total < Decimal("0.00"):
                new_total = Decimal("0.00")

            await self.folio_repo.update_charge(
                charge_id=charge_id,
                description=description,
                amount=amount,
                category=category,
            )

            await self.folio_repo.update_folio_totals(folio_id, new_subtotal, new_total)

            if folio.status.value == "PAID" and new_total > folio.total:
                await self.folio_repo.mark_partially_paid(folio_id)

            await self.db.commit()

            # Fetch updated charge
            updated_charge = await self.folio_repo.get_charge_by_id(folio_id, charge_id)
            staff_name = await self.folio_repo.get_staff_name_by_id(
                updated_charge.posted_by
            )

            return {
                "id": updated_charge.id,
                "folio_id": updated_charge.folio_id,
                "description": updated_charge.description,
                "amount": float(updated_charge.amount),
                "category": updated_charge.category,
                "posted_by": updated_charge.posted_by,
                "posted_by_name": staff_name,
                "posted_at": updated_charge.posted_at,
                "folio_subtotal": float(new_subtotal),
                "folio_total": float(new_total),
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

            booking_result = await self.db.execute(
                select(Booking).where(Booking.id == folio.booking_id)
            )
            booking = booking_result.scalar_one_or_none()
            if booking is None:
                raise BookingException("Associated booking not found")

            if booking.status not in (MasterBookingStatus.CHECKED_IN):
                raise BookingException(
                    f"Cannot delete charge for booking in status {booking.status}. "
                    "Guest must be checked in first."
                )

            await self._verify_staff_property_access(staff_user, booking.property_id)

            if folio.status.value == "WAIVED":
                raise BookingException("Cannot delete charges from a waived folio.")

            # Get charge amount before deleting
            charge = await self.folio_repo.get_charge_by_id(folio_id, charge_id)
            if charge is None:
                raise BookingException("Charge not found.")

            # Calculate new totals before deleting the charge
            old_subtotal = sum(c.amount for c in folio.charges)
            new_subtotal = old_subtotal - charge.amount
            tax_amount = new_subtotal * (folio.tax / Decimal("100"))
            discount_amount = new_subtotal * (folio.discount / Decimal("100"))
            new_total = new_subtotal + tax_amount - discount_amount
            if new_total < Decimal("0.00"):
                new_total = Decimal("0.00")

            deleted = await self.folio_repo.delete_charge(folio_id, charge_id)
            if not deleted:
                raise BookingException("Charge not found.")

            await self.folio_repo.update_folio_totals(folio_id, new_subtotal, new_total)

            await self.db.commit()

            return {
                "folio_id": folio_id,
                "deleted_charge_id": charge_id,
                "folio_subtotal": float(new_subtotal),
                "folio_total": float(new_total),
                "message": "Charge deleted successfully.",
            }

        except (BookingException, PermissionException):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[FolioService] Error deleting charge: {e}")
            raise ServiceException("Could not delete charge.")
