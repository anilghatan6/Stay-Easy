import uuid
from typing import Optional, List
from sqlalchemy import select, delete, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.staff_mgmt.models.staffs_model import Staff, StaffProperty
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class StaffRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── CREATE ──────────────────────────────────────

    async def create_staff(
        self,
        tenant_id: uuid.UUID,
        property_id: uuid.UUID,
        data:dict,
    ) -> Staff:
        logger.info(f"[StaffRepository] Creating staff: {data['email']}")
        try:
            staff = Staff(
                id=data["staff_id"],
                tenant_id=tenant_id,
                full_name=data["full_name"],
                email=data["email"],
                phone_number=data["phone_number"],
                job_role=data["job_role"],
                monthly_salary=data["monthly_salary"],
                joining_date=data["joining_date"],
                status=data["status"],
                photos=data["photos"],
            )
            self.db.add(staff)
            await self.db.flush()  # get staff.id before creating assignment rows

            self.db.add(StaffProperty(
                id=uuid.uuid4(),
                staff_id=staff.id,
                property_id=property_id,
            ))

            logger.info(f"[StaffRepository] Staff created successfully: {staff.id}")
            return staff

        except SQLAlchemyError as e:
            logger.error(f"[StaffRepository] Failed to create staff: {e}")
            raise RepositoryException("Could not create staff member. Please try again.") from e

    # ─── READ ──────────────────────────────────────

    async def get_by_id(self, staff_id: uuid.UUID) -> Optional[Staff]:
        logger.info(f"[StaffRepository] Fetching staff by id: {staff_id}")
        try:
            stmt = (
                select(Staff)
                .options(selectinload(Staff.property_assignments))
                .where(Staff.id == staff_id)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"[StaffRepository] Failed to fetch staff {staff_id}: {e}")
            raise RepositoryException("Could not fetch staff details. Please try again.") from e

    async def get_by_email(self, email: str) -> Optional[Staff]:
        logger.info(f"[StaffRepository] Fetching staff by email: {email}")
        try:
            stmt = select(Staff).where(Staff.email == email)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.error(f"[StaffRepository] Failed to fetch staff by email {email}: {e}")
            raise RepositoryException("Could not fetch staff details. Please try again.") from e

    async def list_by_tenant(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 10
    ) -> tuple[List[Staff], int]:
        logger.info(f"[StaffRepository] Listing staff for tenant: {tenant_id}")
        try:
            stmt = (
                select(Staff)
                .options(selectinload(Staff.property_assignments))
                .where(Staff.tenant_id == tenant_id)
                .order_by(Staff.full_name.asc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            staff_list = result.scalars().all()

            count_query = (
                select(func.count())
                .select_from(Staff)
                .where(Staff.tenant_id == tenant_id)
            )
            count_result = await self.db.execute(count_query)
            total = count_result.scalar_one()

            return staff_list, total

        except SQLAlchemyError as e:
            logger.error(f"[StaffRepository] Failed to list staff for tenant {tenant_id}: {e}")
            raise RepositoryException("Could not fetch staff list. Please try again.") from e

    async def list_by_property(
        self, property_id: uuid.UUID, skip: int = 0, limit: int = 10
    ) -> tuple[List[Staff], int]:
        logger.info(f"[StaffRepository] Listing staff for property: {property_id}")
        try:
            stmt = (
                select(Staff)
                .join(StaffProperty, StaffProperty.staff_id == Staff.id)
                .options(selectinload(Staff.property_assignments))
                .where(StaffProperty.property_id == property_id)
                .order_by(Staff.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            staff_list = result.scalars().unique().all()

            count_stmt = (
                select(func.count())
                .select_from(Staff)
                .join(StaffProperty, StaffProperty.staff_id == Staff.id)
                .where(StaffProperty.property_id == property_id)
            )
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar_one()

            return staff_list, total

        except SQLAlchemyError as e:
            logger.error(f"[StaffRepository] Failed to list staff for property {property_id}: {e}")
            raise RepositoryException("Could not fetch staff list. Please try again.") from e

    # ─── UPDATE ──────────────────────────────────────

    async def update_staff_fields(self, staff_id: uuid.UUID, update_data: dict) -> Optional[Staff]:
        """Applies scalar field updates (not property assignments) to a staff record."""
        logger.info(f"[StaffRepository] Updating staff fields: {staff_id}")
        try:
            staff = await self.get_by_id(staff_id)
            if staff is None:
                return None

            for field, value in update_data.items():
                setattr(staff, field, value)
            
            return staff

        except SQLAlchemyError as e:
            logger.error(f"[StaffRepository] Failed to update staff {staff_id}: {e}")
            raise RepositoryException("Could not update staff member. Please try again.") from e

    # ─── DELETE ──────────────────────────────────────

    async def delete_staff(self, staff_id: uuid.UUID) -> bool:
        logger.info(f"[StaffRepository] Deleting staff: {staff_id}")
        try:
            staff = await self.get_by_id(staff_id)
            if staff is None:
                return False

            await self.db.delete(staff)  # cascade handles StaffProperty rows
            logger.info(f"[StaffRepository] Staff deleted successfully: {staff_id}")
            return True

        except SQLAlchemyError as e:
            logger.error(f"[StaffRepository] Failed to delete staff {staff_id}: {e}")
            raise RepositoryException("Could not delete staff member. Please try again.") from e