from fastapi import Depends
from app.modules.staff_mgmt.services.staffs_services import StaffService
from app.modules.staff_mgmt.repositories.staffs_repository import StaffRepository
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.services.image_services import ImageService
from app.config.database_config import get_db
from sqlalchemy.ext.asyncio import AsyncSession


def get_staff_repository(db: AsyncSession = Depends(get_db)) -> StaffRepository:
    return StaffRepository(db)


def get_property_repository(db: AsyncSession = Depends(get_db)) -> PropertyRepository:
    return PropertyRepository(db)

def get_image_service():
    return ImageService()

def get_staff_service(
    db: AsyncSession = Depends(get_db),
    staff_repo: StaffRepository = Depends(get_staff_repository),
    property_repo: PropertyRepository = Depends(get_property_repository),
    image_service: ImageService = Depends(get_image_service),
) -> StaffService:
    return StaffService(db=db, staff_repo=staff_repo, prop_repo=property_repo, image_service=image_service)





