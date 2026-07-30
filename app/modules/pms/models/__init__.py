from .tenants_model import Tenant
from .properties_model import (
Property,
Amenity,
)
from .offers_model import (
SpecialOffer
)
from .discount_code_model import (
    DiscountCode
)
from .rooms_model import (
    Rooms,
    RoomType,
    BedType
)

__all__ = [
 "Tenant",
 "Property",
 "Amenity",
 "SpecialOffer",
 "DiscountCode",
 "Rooms",
 "RoomType",
 "BedType"
 
]
