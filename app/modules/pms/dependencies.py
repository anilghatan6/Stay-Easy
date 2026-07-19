from app.modules.pms.services.tenant_services import TenantService
from app.modules.pms.repositories.tenants_repo import TenantRepository

from app.modules.pms.services.properties_scervices import PropertyService
from app.modules.pms.repositories.properties_repo import PropertyRepository

from app.modules.pms.services.room_services import RoomService
from app.modules.pms.repositories.room_repo import RoomRepository

from app.modules.pms.repositories.offers_repo import SpecialOfferRepository
from app.modules.pms.services.offers_services import SpecialOfferService

from app.modules.pms.services.image_services import ImageService


from app.modules.pms.repositories.discount_code_repo import DiscountCodeRepository
from app.modules.pms.services.discount_code_service import DiscountCodeService

from app.config.database_config import get_db
from fastapi import Depends


def get_image_service() -> ImageService:
    return ImageService()


def get_tenant_service(db=Depends(get_db)) -> TenantService:
    return TenantService(tenant_repo=TenantRepository(db=db))


def get_property_service(db=Depends(get_db)) -> PropertyService:
    return PropertyService(
        property_repo=PropertyRepository(db=db),
        image_service=get_image_service(),
    )


def get_room_service(db=Depends(get_db)) -> RoomService:
    return RoomService(
        room_repo=RoomRepository(db=db),
        property_repo=PropertyRepository(db=db),
        image_service=get_image_service(),
    )


def get_special_offer_service(db=Depends(get_db)) -> SpecialOfferService:
    return SpecialOfferService(special_offer_repo=SpecialOfferRepository(db=db))


def get_discount_code_service(db=Depends(get_db)) -> DiscountCodeService:
    return DiscountCodeService(discount_code_repo=DiscountCodeRepository(db=db))
