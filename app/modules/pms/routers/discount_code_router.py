from fastapi import APIRouter, Depends, HTTPException, status
import uuid
from app.modules.pms.schemas.discount_code_schema import DiscountCodeCreate, DiscountCodeResponse,DiscountCodeUpdate
from app.modules.pms.services.discount_code_service import DiscountCodeService
from app.modules.auth.auth_middlewares import CurrentUser
from app.utils.schemas import StandardResponse
from app.modules.pms.dependencies import get_discount_code_service

router = APIRouter(prefix="/properties/{property_id}/discount-codes", tags=["Discount Codes"])

@router.post("/", response_model=StandardResponse[DiscountCodeResponse], status_code=status.HTTP_201_CREATED)
async def create_discount_code(
    user: CurrentUser,
    property_id: uuid.UUID,
    payload: DiscountCodeCreate,
    discount_code_service: DiscountCodeService = Depends(get_discount_code_service)
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to add discount code. You must belong to an active tenant.",
        )
    
    created_discount = await discount_code_service.create_discount_code(property_id=property_id, payload=payload)
    
    return {
        "success":True,
        "data":created_discount
    }

@router.get("/",response_model=StandardResponse[list[DiscountCodeResponse]],status_code=status.HTTP_200_OK)
async def get_all_discount_codes(user:CurrentUser,property_id:uuid.UUID,discount_code_service:DiscountCodeService = Depends(get_discount_code_service)):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to get discount codes. You must belong to an active tenant.",
        )
    
    all_discount_codes = await discount_code_service.get_all_discount_codes(property_id=property_id)
    
    return {
        "success":True,
        "data":all_discount_codes
    }

@router.get("/{discount_id}",response_model=StandardResponse[DiscountCodeResponse], status_code=status.HTTP_200_OK)
async def get_discount_code(
    property_id: uuid.UUID,
    discount_id: uuid.UUID,
    user:CurrentUser,
    discount_code_service:DiscountCodeService = Depends(get_discount_code_service)
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to get discount code. You must belong to an active tenant.",
        )
    
    discount_code = await discount_code_service.get_discount_code(property_id=property_id, discount_id=discount_id)
    
    return {
        "success":True,
        "data":discount_code
    }

@router.patch("/{discount_id}",response_model=StandardResponse[DiscountCodeResponse], status_code=status.HTTP_200_OK)
async def update_discount_code(
    property_id: uuid.UUID,
    discount_id: uuid.UUID,
    user:CurrentUser,
    payload:DiscountCodeUpdate,
    discount_code_service:DiscountCodeService = Depends(get_discount_code_service)
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to update discount code. You must belong to an active tenant.",
        )
    
    updated_discount = await discount_code_service.update_discount_code(property_id=property_id, discount_id=discount_id, payload=payload)
    
    return {
        "success":True,
        "data":updated_discount
    }

@router.delete("/{discount_id}",status_code=status.HTTP_200_OK)
async def delete_discount_code(
    property_id: uuid.UUID,
    discount_id: uuid.UUID,
    user:CurrentUser,
    discount_code_service:DiscountCodeService = Depends(get_discount_code_service)
):
    if user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not authorized to delete discount code. You must belong to an active tenant.",
        )
    
    await discount_code_service.delete_discount_code(property_id=property_id, discount_id=discount_id)
    
    return {
        "success":True,
        "message":"Discount Code deleted successfully"
    }
