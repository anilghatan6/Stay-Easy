import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pms.repositories.review_repository import ReviewRepository
from app.modules.auth.models.guests_model import Guest
from app.utils.exceptions import BookingException, RepositoryException, ServiceException
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class ReviewService:
    def __init__(self, db: AsyncSession, review_repo: ReviewRepository):
        self.db = db
        self.review_repo = review_repo

    async def create_review(
        self,
        property_id: uuid.UUID,
        guest: Guest,
        booking_id: uuid.UUID,
        rating: int,
        comment: str | None,
    ) -> dict:
        """Create a review for a property after a completed stay."""
        logger.info(f"[ReviewService] Creating review for property {property_id}")
        try:
            # 1. Verify the guest has a CHECKED_OUT booking at this property
            booking = await self.review_repo.get_checked_out_booking_for_guest(
                property_id, guest.id
            )
            if booking is None:
                raise BookingException(
                    "You can only review properties where you have completed a stay"
                )

            # 2. Allow linking to a specific booking, or auto-find one
            if booking_id is not None:
                # Verify the provided booking_id is valid for this guest/property
                if booking.id != booking_id:
                    # Check if the specific booking exists and is checked out
                    from app.modules.booking.models.booking_model import Booking, MasterBookingStatus
                    from sqlalchemy import select

                    stmt = select(Booking).where(
                        Booking.id == booking_id,
                        Booking.property_id == property_id,
                        Booking.guest_id == guest.id,
                        Booking.status == MasterBookingStatus.CHECKED_OUT,
                    )
                    result = await self.db.execute(stmt)
                    booking = result.scalar_one_or_none()
                    if booking is None:
                        raise BookingException(
                            "Invalid booking. You can only review after checkout."
                        )

            # 3. Check no existing review for this booking
            existing = await self.review_repo.get_review_by_booking(booking.id)
            if existing is not None:
                raise BookingException("You have already reviewed this stay")

            # 4. Create the review
            review = await self.review_repo.create_review(
                property_id=property_id,
                guest_id=guest.id,
                booking_id=booking.id,
                rating=rating,
                comment=comment,
            )

            # 5. Update property rating
            await self.review_repo.update_property_rating(property_id)

            await self.db.commit()

            return {
                "id": review.id,
                "property_id": review.property_id,
                "guest_name": guest.full_name,
                "rating": review.rating,
                "comment": review.comment,
                "is_edited": review.is_edited,
                "created_at": review.created_at,
                "updated_at": review.updated_at,
            }

        except BookingException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[ReviewService] Error creating review: {e}")
            raise ServiceException("Could not create review. Please try again.")

    async def edit_review(
        self,
        review_id: uuid.UUID,
        guest: Guest,
        rating: int | None,
        comment: str | None,
    ) -> dict:
        """Edit an existing review."""
        logger.info(f"[ReviewService] Editing review {review_id}")
        try:
            review = await self.review_repo.get_review_by_id(review_id)
            if review is None:
                raise BookingException("Review not found")

            if review.guest_id != guest.id:
                raise BookingException("You can only edit your own reviews")

            updated = await self.review_repo.update_review(
                review_id=review_id,
                rating=rating,
                comment=comment,
            )

            if updated is None:
                raise BookingException("Review not found")

            # Recalculate property rating
            await self.review_repo.update_property_rating(review.property_id)

            await self.db.commit()
            await self.db.refresh(updated)

            return {
                "id": updated.id,
                "property_id": updated.property_id,
                "guest_name": guest.full_name,
                "rating": updated.rating,
                "comment": updated.comment,
                "is_edited": updated.is_edited,
                "created_at": updated.created_at,
                "updated_at": updated.updated_at,
            }

        except BookingException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"[ReviewService] Error editing review: {e}")
            raise ServiceException("Could not edit review. Please try again.")

    async def get_reviews_for_property(
        self, property_id: uuid.UUID, skip: int, limit: int
    ) -> dict:
        """Get paginated reviews for a property with rating summary."""
        logger.info(f"[ReviewService] Getting reviews for property {property_id}")
        try:
            reviews, total = await self.review_repo.get_reviews_by_property(
                property_id, skip, limit
            )

            avg_rating, total_reviews = await self.review_repo.get_review_stats(
                property_id
            )

            review_items = [
                {
                    "id": r.id,
                    "property_id": r.property_id,
                    "guest_name": r.guest.full_name if r.guest else "Anonymous",
                    "rating": r.rating,
                    "comment": r.comment,
                    "is_edited": r.is_edited,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in reviews
            ]

            return {
                "reviews": review_items,
                "average_rating": round(avg_rating, 2),
                "total_reviews": total_reviews,
            }

        except Exception as e:
            logger.error(f"[ReviewService] Error getting reviews: {e}")
            raise ServiceException("Could not fetch reviews. Please try again.")


    async def get_review(
        self,
        review_id: uuid.UUID,
        guest_id:uuid.UUID
    ) -> dict:
        """Get a review for a property."""
        logger.info(f"[ReviewService] Getting review {review_id}")
        try:
            review = await self.review_repo.get_review_by_id(review_id)
            if review is None:
                raise BookingException("Review not found")

            if review.guest_id != guest_id:
                raise BookingException("You can only view your own reviews")

            return {
                "id": review.id,
                "property_id": review.property_id,
                "guest_name": review.guest.full_name if review.guest else "Anonymous",
                "rating": review.rating,
                "comment": review.comment,
                "is_edited": review.is_edited,
                "created_at": review.created_at,
                "updated_at": review.updated_at,
            }

        except BookingException:
            raise
        except Exception as e:
            logger.error(f"[ReviewService] Error getting review: {e}")
            raise ServiceException("Could not fetch review. Please try again.")
