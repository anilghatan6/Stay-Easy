import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select, update, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.booking.models.folio_models import Folio, FolioCharge
from app.modules.booking.models.booking_model import Booking, BookingRoom
from app.modules.auth.models.users_model import User
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class FolioRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─────────────────────── FOLIO QUERIES ─────────────────────────

    async def create_folio(
        self,
        booking_id: uuid.UUID,
        guest_id: uuid.UUID,
        tax: Decimal = Decimal("0.00"),
        discount: Decimal = Decimal("0.00"),
    ) -> Folio:
        logger.info(f"[FolioRepository] Creating folio for booking {booking_id}")
        try:
            folio = Folio(
                booking_id=booking_id,
                guest_id=guest_id,
                tax=tax,
                discount=discount,
                subtotal=Decimal("0.00"),
                total=Decimal("0.00"),
            )
            self.db.add(folio)
            await self.db.flush()
            await self.db.refresh(folio)
            return folio
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[FolioRepository] Failed to create folio: {e}")
            raise RepositoryException("Failed to create folio.")

    async def get_folio_by_id(self, folio_id: uuid.UUID) -> Optional[Folio]:
        logger.info(f"[FolioRepository] Getting folio {folio_id}")
        try:
            stmt = (
                select(Folio)
                .where(Folio.id == folio_id)
                .options(selectinload(Folio.charges))
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to get folio: {e}")
            raise RepositoryException("Failed to fetch folio.")

    async def get_folio_by_booking_id(self, booking_id: uuid.UUID) -> Optional[Folio]:
        logger.info(f"[FolioRepository] Getting folio for booking {booking_id}")
        try:
            stmt = (
                select(Folio)
                .where(Folio.booking_id == booking_id)
                .options(selectinload(Folio.charges))
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to get folio by booking: {e}")
            raise RepositoryException("Failed to fetch folio for booking.")

    async def get_folios_by_property(
        self,
        property_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Folio], int]:
        logger.info(f"[FolioRepository] Getting folios for property {property_id}")
        try:
            # Join folios -> bookings to filter by property_id
            count_stmt = (
                select(func.count())
                .select_from(Folio)
                .join(Booking, Booking.id == Folio.booking_id)
                .where(Booking.property_id == property_id)
            )
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            stmt = (
                select(Folio)
                .join(Booking, Booking.id == Folio.booking_id)
                .where(Booking.property_id == property_id)
                .options(selectinload(Folio.charges))
                .order_by(Folio.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            folios = result.scalars().all()
            return folios, total
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to get folios: {e}")
            raise RepositoryException("Failed to fetch folios.")

    async def update_folio_totals(
        self,
        folio_id: uuid.UUID,
        subtotal: Decimal,
        total: Decimal,
    ) -> None:
        logger.info(f"[FolioRepository] Updating folio totals for {folio_id}")
        try:
            await self.db.execute(
                update(Folio)
                .where(Folio.id == folio_id)
                .values(subtotal=subtotal, total=total)
            )
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to update folio totals: {e}")
            raise RepositoryException("Failed to update folio totals.")

    async def update_folio_tax_discount(
        self,
        folio_id: uuid.UUID,
        tax: Decimal,
        discount: Decimal,
    ) -> None:
        logger.info(f"[FolioRepository] Updating folio tax/discount for {folio_id}")
        try:
            await self.db.execute(
                update(Folio)
                .where(Folio.id == folio_id)
                .values(tax=tax, discount=discount)
            )
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to update folio: {e}")
            raise RepositoryException("Failed to update folio.")

    async def settle_folio(self, folio_id: uuid.UUID) -> None:
        logger.info(f"[FolioRepository] Settling folio {folio_id}")
        try:
            await self.db.execute(
                update(Folio)
                .where(Folio.id == folio_id)
                .values(
                    status="PAID",
                    settled_at=datetime.utcnow(),
                )
            )
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to settle folio: {e}")
            raise RepositoryException("Failed to settle folio.")

    async def waive_folio(self, folio_id: uuid.UUID) -> None:
        logger.info(f"[FolioRepository] Waiving folio {folio_id}")
        try:
            await self.db.execute(
                update(Folio)
                .where(Folio.id == folio_id)
                .values(
                    status="WAIVED",
                    total=Decimal("0.00"),
                    settled_at=datetime.utcnow(),
                )
            )
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to waive folio: {e}")
            raise RepositoryException("Failed to waive folio.")

    # ─────────────────────── CHARGE QUERIES ─────────────────────────

    async def add_charge(
        self,
        folio_id: uuid.UUID,
        description: str,
        amount: Decimal,
        category: str,
        posted_by: uuid.UUID,
    ) -> FolioCharge:
        logger.info(f"[FolioRepository] Adding charge to folio {folio_id}")
        try:
            charge = FolioCharge(
                folio_id=folio_id,
                description=description,
                amount=amount,
                category=category,
                posted_by=posted_by,
                posted_at=datetime.utcnow(),
            )
            self.db.add(charge)
            await self.db.flush()
            await self.db.refresh(charge)
            return charge
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[FolioRepository] Failed to add charge: {e}")
            raise RepositoryException("Failed to add charge.")

    async def get_charges_by_folio_id(
        self, folio_id: uuid.UUID
    ) -> Sequence[FolioCharge]:
        logger.info(f"[FolioRepository] Getting charges for folio {folio_id}")
        try:
            stmt = (
                select(FolioCharge)
                .where(FolioCharge.folio_id == folio_id)
                .order_by(FolioCharge.posted_at.asc())
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to get charges: {e}")
            raise RepositoryException("Failed to fetch charges.")

    async def get_charge_by_id(
        self, folio_id: uuid.UUID, charge_id: uuid.UUID
    ) -> Optional[FolioCharge]:
        logger.info(f"[FolioRepository] Getting charge {charge_id}")
        try:
            stmt = select(FolioCharge).where(
                FolioCharge.id == charge_id,
                FolioCharge.folio_id == folio_id,
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to get charge: {e}")
            raise RepositoryException("Failed to fetch charge.")

    async def update_charge(
        self,
        charge_id: uuid.UUID,
        description: Optional[str] = None,
        amount: Optional[Decimal] = None,
        category: Optional[str] = None,
    ) -> None:
        logger.info(f"[FolioRepository] Updating charge {charge_id}")
        try:
            values = {}
            if description is not None:
                values["description"] = description
            if amount is not None:
                values["amount"] = amount
            if category is not None:
                values["category"] = category

            if values:
                await self.db.execute(
                    update(FolioCharge)
                    .where(FolioCharge.id == charge_id)
                    .values(**values)
                )
        except SQLAlchemyError as e:
            logger.error(f"[FolioRepository] Failed to update charge: {e}")
            raise RepositoryException("Failed to update charge.")

    async def delete_charge(self, folio_id: uuid.UUID, charge_id: uuid.UUID) -> bool:
        logger.info(f"[FolioRepository] Deleting charge {charge_id}")
        try:
            charge = await self.get_charge_by_id(folio_id, charge_id)
            if charge is None:
                return False
            await self.db.delete(charge)
            return True
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"[FolioRepository] Failed to delete charge: {e}")
            raise RepositoryException("Failed to delete charge.")

    async def get_staff_name_by_id(self, staff_id: uuid.UUID) -> Optional[str]:
        """Resolve staff display name from User table."""
        try:
            result = await self.db.execute(
                select(User.full_name, User.email).where(User.id == staff_id)
            )
            row = result.first()
            if row:
                return row[0] or row[1]
            return None
        except SQLAlchemyError:
            return None
