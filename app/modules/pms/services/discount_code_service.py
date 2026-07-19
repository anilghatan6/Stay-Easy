import uuid
from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository
from app.modules.pms.schemas.discount_code_schema import (
    DiscountCodeCreate,
    DiscountCodeResponse,
    DiscountCodeUpdate,
)

from app.utils.logging import LoggerFactory
from app.utils.exceptions import (
    ServiceException,
    RepositoryException,
    DiscountCodeAlreadyExistException,
    DiscountCodeNotFoundException,
    DiscountCodeValidationError,
)

from app.modules.pms.models.discount_code_model import DiscountType

logger = LoggerFactory.get_logger(__name__)


class DiscountCodeService:
    def __init__(self, discount_code_repo: DiscountCodeRepository):
        self.discount_code_repo = discount_code_repo

    async def _exists_by_code(self, property_id: uuid.UUID, code: str) -> bool:
        logger.info(
            f"[DiscountCodeService] Checking existence for code '{code}' under property {property_id}"
        )

        try:
            db_discount = await self.discount_code_repo.get_discount_code(
                property_id, code
            )
            return True if db_discount else False
        except RepositoryException:
            raise

        except Exception as e:
            logger.error(f"[DiscountCodeService] Error checking existence: {str(e)}")
            raise ServiceException(str(e))

    async def create_discount_code(
        self, property_id: uuid.UUID, payload: DiscountCodeCreate
    ):
        logger.info(
            f"[DiscountCodeService] Commencing registration process for property: {property_id}"
        )
        discount_code_data = payload.model_dump()
        discount_code_data["property_id"] = property_id

        try:
            exists = await self._exists_by_code(property_id, discount_code_data["code"])
            if exists:
                logger.warning(
                    f"[DiscountCodeService] Validation rejected. '{discount_code_data['code']}' already exists under property scope '{property_id}'."
                )
                raise DiscountCodeAlreadyExistException(
                    f"Discount code '{discount_code_data['code']}' already exists."
                )

            # 2. Delegate insertion processing task to the repository layer
            result = await self.discount_code_repo.create_discount_code(
                discount_code_data
            )

            # 3. Commit transaction on the DB session managed by the service block context
            await self.discount_code_repo.db.commit()
            await self.discount_code_repo.db.refresh(result)

            logger.info(
                "[DiscountCodeService] Discount code registered and committed successfully."
            )
            return DiscountCodeResponse.model_validate(result)

        except (DiscountCodeAlreadyExistException, RepositoryException) as e:
            await self.discount_code_repo.db.rollback()
            logger.error(
                f"[DiscountCodeService] Failed to create discount code: {str(e)}"
            )
            raise

        except Exception as e:
            await self.discount_code_repo.db.rollback()
            logger.error(
                f"[DiscountCodeService] Critical failure encountered during creation: {str(e)}"
            )
            raise ServiceException(f"An unexpected internal error occurred: {str(e)}")

    async def get_all_discount_codes(self, property_id: uuid.UUID):
        logger.info(
            f"[DiscountCodeService] Fetching all discount codes for property: {property_id}"
        )
        try:
            all_discount_codes = await self.discount_code_repo.get_all_discount_codes(
                property_id
            )
            return [
                DiscountCodeResponse.model_validate(discount_code)
                for discount_code in all_discount_codes
            ]
        except RepositoryException:
            raise
        except Exception as e:
            logger.error(
                f"[DiscountCodeService] Error fetching discount codes: {str(e)}"
            )
            raise ServiceException(str(e))

    async def get_discount_code(self, property_id: uuid.UUID, discount_id: uuid.UUID):
        logger.info(
            f"[DiscountCodeService] Fetching discount code for property: {property_id} and discount code: {discount_id}"
        )
        try:
            db_discount = await self.discount_code_repo.get_discount_code_by_id(
                property_id, discount_id
            )
            if not db_discount:
                logger.info(
                    f"[DiscountCodeService] Discount code '{discount_id}' not found for property: {property_id}"
                )
                raise DiscountCodeNotFoundException("Discount code not found")

            logger.info(
                f"[DiscountCodeService] Discount code '{discount_id}' fetched successfully for property: {property_id}"
            )
            return DiscountCodeResponse.model_validate(db_discount)

        except (DiscountCodeNotFoundException, RepositoryException):
            raise
        except Exception as e:
            logger.error(
                f"[DiscountCodeService] Error fetching discount code: {str(e)}"
            )
            raise ServiceException(f"An unexpected internal error occurred: {str(e)}")

    async def update_discount_code(
        self,
        property_id: uuid.UUID,
        discount_id: uuid.UUID,
        payload: DiscountCodeUpdate,
    ) -> DiscountCodeResponse:
        """Handles stateful business merging validations and pushes partial updates to the database."""
        logger.info(
            f"[DiscountCodeService] Updating discount code for property: {property_id} and discount code: {discount_id}"
        )
        try:
            # 1. Fetch current database record
            db_discount = await self.discount_code_repo.get_discount_code_by_id(
                property_id, discount_id
            )
            if not db_discount:
                logger.warning(
                    f"Discount code '{discount_id}' not found for property: {property_id}"
                )
                raise DiscountCodeNotFoundException("Discount code not found")

            # 2. Extract changes (Exit early if payload is empty)
            update_data = payload.model_dump(exclude_unset=True)
            if not update_data:
                logger.info("No updated data provided")
                return DiscountCodeResponse.model_validate(db_discount)

            # Verify code uniqueness only if it is explicitly changing to a new value
            if "code" in update_data:
                new_code = update_data["code"].strip().upper()
                if new_code != db_discount.code:
                    exist = await self._exists_by_code(property_id, new_code)
                    if exist:
                        logger.warning(
                            f"Discount code '{new_code}' already exists for property: {property_id}"
                        )
                        raise DiscountCodeAlreadyExistException(
                            f"Discount code '{new_code}' already exists"
                        )

            # 3. Merge State Validation: Combine incoming changes with existing DB records
            final_type = update_data.get("type", db_discount.type)
            final_value = update_data.get("discount_value", db_discount.discount_value)
            final_min = update_data.get("min_amount", db_discount.min_amount)
            final_from = update_data.get("valid_from", db_discount.valid_from)
            final_to = update_data.get("valid_to", db_discount.valid_to)

            # Enforce combined system rules
            if final_to <= final_from:
                raise DiscountCodeValidationError(
                    "The expiration date must occur after the start date."
                )

            if final_type == DiscountType.PERCENTAGE and final_value > 100:
                raise DiscountCodeValidationError(
                    "Percentage discount values cannot exceed 100%."
                )

            if final_type == DiscountType.FIXED and final_value > final_min:
                raise DiscountCodeValidationError(
                    "Fixed discount cannot be greater than the minimum required spend."
                )

            # 4. Save and Commit using your Repository session link bindings
            updated_record = await self.discount_code_repo.update_discount_code(
                db_discount, update_data
            )
            await self.discount_code_repo.db.commit()
            await self.discount_code_repo.db.refresh(updated_record)

            return DiscountCodeResponse.model_validate(updated_record)

        except (
            DiscountCodeNotFoundException,
            DiscountCodeAlreadyExistException,
            DiscountCodeValidationError,
            RepositoryException,
        ):
            await self.discount_code_repo.db.rollback()
            raise
        except Exception as e:
            await self.discount_code_repo.db.rollback()
            logger.error(
                f"[DiscountCodeService] Unexpected failure during update: {str(e)}"
            )
            raise ServiceException(f"An unexpected internal error occurred: {str(e)}")

    async def delete_discount_code(
        self, property_id: uuid.UUID, discount_id: uuid.UUID
    ) -> None:

        logger.info(
            f"[DiscountCodeService] Initiating deletion process for discount {discount_id} under property {property_id}"
        )
        try:
            # 1. Fetch current database record to inspect business metrics
            db_discount = await self.discount_code_repo.get_discount_code_by_id(
                property_id, discount_id
            )
            if not db_discount:
                logger.warning(
                    f"[DiscountCodeService] Delete failed. Discount code '{discount_id}' not found."
                )
                raise DiscountCodeNotFoundException("Discount code not found")

            # 2. Business Rule: Guard historical tracking data (Block deletion if already used)
            # if db_discount.used_count > 0:
            #     logger.warning(f"[DiscountCodeService] Delete rejected. Discount '{discount_id}' has a used_count of {db_discount.used_count}.")
            #     raise DiscountCodeValidationError("Cannot delete this discount code because it has already been used by customers.")

            # 3. Proceed to repository layer for database execution
            await self.discount_code_repo.delete_discount_code(property_id, discount_id)

            # 4. Commit transaction safely
            await self.discount_code_repo.db.commit()
            logger.info(
                f"[DiscountCodeService] Discount code '{discount_id}' deleted and committed successfully."
            )

        except (
            DiscountCodeNotFoundException,
            DiscountCodeValidationError,
            RepositoryException,
        ):
            await self.discount_code_repo.db.rollback()
            raise
        except Exception as e:
            await self.discount_code_repo.db.rollback()
            logger.error(
                f"[DiscountCodeService] Unexpected failure during deletion: {str(e)}"
            )
            raise ServiceException(f"An unexpected internal error occurred: {str(e)}")
