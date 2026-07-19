from typing import Generic, TypeVar
from pydantic import BaseModel
from typing import Optional, Any

# Create a generic type variable
DataType = TypeVar("DataType")


class StandardResponse(BaseModel, Generic[DataType]):
    success: bool = True
    data: DataType
    meta: Optional[dict[str, Any]] = None
