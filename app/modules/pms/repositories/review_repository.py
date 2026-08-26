import uuid
from decimal import Decimal
from sqlalchemy import select, func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.pms.models.review_model import Review
from app.modules.pms.models.properties_model import Property
from app.modules.booking.models.booking_model import Booking, MasterBookingStatus
from app.utils.exceptions import RepositoryException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class ReviewRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_checked_out_booking_for_guest(
        self, property_id: uuid.UUID, guest_id: uuid.UUID
    ) -> Booking | None:
        """Find a CHECKED_OUT booking for this guest at this property."""
        logger.info("[ReviewRepository] Finding checked-out booking for guest")
        try:
            stmt = select(Booking).where(
                Booking.property_id == property_id,
                Booking.guest_id == guest_id,
                Booking.status == MasterBookingStatus.CHECKED_OUT,
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[ReviewRepository] Failed to find booking: {e}")
            raise RepositoryException("Could not verify booking history.")

    async def get_review_by_booking(self, booking_id: uuid.UUID) -> Review | None:
        """Check if a review already exists for this booking."""
        logger.info("[ReviewRepository] Checking for existing review")
        try:
            stmt = select(Review).where(Review.booking_id == booking_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[ReviewRepository] Failed to check review: {e}")
            raise RepositoryException("Could not check existing review.")

    async def create_review(
        self,
        property_id: uuid.UUID,
        guest_id: uuid.UUID,
        booking_id: uuid.UUID,
        rating: int,
        comment: str | None,
    ) -> Review:
        """Create a new review."""
        logger.info("[ReviewRepository] Creating review")
        try:
            review = Review(
                id=uuid.uuid4(),
                property_id=property_id,
                guest_id=guest_id,
                booking_id=booking_id,
                rating=rating,
                comment=comment,
                is_edited=False,
            )
            self.db.add(review)
            await self.db.flush()
            return review
        except SQLAlchemyError as e:
            logger.error(f"[ReviewRepository] Failed to create review: {e}")
            raise RepositoryException("Could not create review.")

    async def get_review_by_id(self, review_id: uuid.UUID) -> Review | None:
        """Get a review by ID with guest loaded."""
        logger.info("[ReviewRepository] Fetching review by ID")
        try:
            stmt = (
                select(Review)
                .options(joinedload(Review.guest))
                .where(Review.id == review_id)
            )
            result = await self.db.execute(stmt)
            return result.unique().scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"[ReviewRepository] Failed to fetch review: {e}")
            raise RepositoryException("Could not fetch review.")

    async def update_review(
        self,
        review_id: uuid.UUID,
        rating: int | None,
        comment: str | None,
    ) -> Review | None:
        """Update a review's rating and/or comment."""
        logger.info("[ReviewRepository] Updating review")
        try:
            result = await self.db.execute(
                select(Review)
                .where(Review.id == review_id)
                .with_for_update()
            )
            review = result.scalar_one_or_none()

            if review is None:
                return None

            if rating is not None:
                review.rating = rating
            if comment is not None:
                review.comment = comment
            review.is_edited = True

            return review
        except SQLAlchemyError as e:
            logger.error(f"[ReviewRepository] Failed to update review: {e}")
            raise RepositoryException("Could not update review.")

    async def get_reviews_by_property(
        self, property_id: uuid.UUID, skip: int, limit: int
    ) -> tuple[list[Review], int]:
        """Get paginated reviews for a property with guest info."""
        logger.info("[ReviewRepository] Fetching reviews for property")
        try:
            stmt = (
                select(Review)
                .options(joinedload(Review.guest))
                .where(Review.property_id == property_id)
                .order_by(Review.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            reviews = result.unique().scalars().all()

            count_stmt = (
                select(func.count())
                .select_from(Review)
                .where(Review.property_id == property_id)
            )
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            return list(reviews), total
        except SQLAlchemyError as e:
            logger.error(f"[ReviewRepository] Failed to fetch reviews: {e}")
            raise RepositoryException("Could not fetch reviews.")

    async def get_review_stats(
        self, property_id: uuid.UUID
    ) -> tuple[float, int]:
        """Get average rating and total review count for a property."""
        logger.info("[ReviewRepository] Getting review stats")
        try:
            stmt = select(
                func.coalesce(func.avg(Review.rating), 0).label("avg_rating"),
                func.count(Review.id).label("total"),
            ).where(Review.property_id == property_id)
            result = await self.db.execute(stmt)
            row = result.one()
            return float(row.avg_rating), row.total
        except SQLAlchemyError as e:
            logger.error(f"[ReviewRepository] Failed to get review stats: {e}")
            raise RepositoryException("Could not get review statistics.")

    async def update_property_rating(self, property_id: uuid.UUID) -> None:
        """Recalculate and update the property's average_rating and total_reviews."""
        logger.info(f"[ReviewRepository] Updating property rating for {property_id}")
        try:
            avg_rating, total_reviews = await self.get_review_stats(property_id)

            await self.db.execute(
                update(Property)
                .where(Property.id == property_id)
                .values(
                    average_rating=Decimal(str(round(avg_rating, 2))),
                    total_reviews=total_reviews,
                )
            )
        except SQLAlchemyError as e:
            logger.error(f"[ReviewRepository] Failed to update property rating: {e}")
            raise RepositoryException("Could not update property rating.")
