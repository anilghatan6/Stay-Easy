import uuid
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, status

from app.modules.housekeeping_mobile.auth import CurrentHousekeepingStaff
from app.middlewares.auth_middlewares import CurrentUser
from app.modules.housekeeping_mobile.schemas.cleaning_schemas import (
    CleaningSubmissionResponse,
    SupplierUsage,
    SupervisorReviewRequest,
)
from app.modules.housekeeping_mobile.services.cleaning_service import CleaningService
from app.modules.housekeeping_mobile.dependencies import get_cleaning_service
from app.modules.housekeeping_mobile.models.cleaning_submission_model import (
    CleaningChecklistItem,
    CleaningSubmissionStatus,
)
from app.utils.schemas import StandardResponse
from app.utils.validation import verify_tenant

router = APIRouter(
    prefix="/properties/{property_id}/housekeeping/cleaning",
    tags=["housekeeping-mobile-cleaning"],
)


@router.post(
    "/submit",
    response_model=StandardResponse[CleaningSubmissionResponse],
    status_code=status.HTTP_201_CREATED,
    description="Submit cleaning results for supervisor inspection",
)
async def submit_for_inspection(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    task_id: uuid.UUID = Form(...),
    checklist_items: str = Form(
        ...,
        description='JSON array of checklist items, e.g. ["BED_MAKING","BATHROOM_CLEANING"]',
    ),
    suppliers_used: str = Form(
        default="[]",
        description='JSON array of suppliers, e.g. [{"item":"TOWELS","quantity":4}]',
    ),
    before_images: Optional[List[UploadFile]] = File(
        None, max_length=5, description="Before cleaning images"
    ),
    after_images: Optional[List[UploadFile]] = File(
        None, max_length=5, description="After cleaning images"
    ),
    cleaning_service: CleaningService = Depends(get_cleaning_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import (
        MobileTaskRepository,
    )

    task_repo = MobileTaskRepository(cleaning_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    # Parse JSON form data
    try:
        checklist_parsed = json.loads(checklist_items)
        checklist_enum = [CleaningChecklistItem(i) for i in checklist_parsed]
    except (json.JSONDecodeError, ValueError) as e:
        return {"success": False, "data": None, "message": f"Invalid checklist_items: {e}"}

    try:
        suppliers_parsed = json.loads(suppliers_used)
        suppliers_list = [SupplierUsage(**s) for s in suppliers_parsed]
    except (json.JSONDecodeError, ValueError) as e:
        return {"success": False, "data": None, "message": f"Invalid suppliers_used: {e}"}

    result = await cleaning_service.submit_for_inspection(
        staff_id=staff.id,
        property_id=property_id,
        task_id=task_id,
        checklist_items=checklist_enum,
        suppliers_used=suppliers_list,
        before_files=before_images,
        after_files=after_images,
    )
    return {"success": True, "data": result}


@router.get(
    "",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="Get cleaning submissions made by the logged-in housekeeping staff",
)
async def get_my_submissions(
    property_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    cleaning_service: CleaningService = Depends(get_cleaning_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import (
        MobileTaskRepository,
    )

    task_repo = MobileTaskRepository(cleaning_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": [], "message": "Staff profile not found"}

    result, total = await cleaning_service.get_my_submissions(
        staff.id, property_id, skip, limit
    )
    has_more = (skip + len(result)) < total
    return {
        "success": True,
        "data": result,
        "meta": {"total": total, "skip": skip, "limit": limit, "has_more": has_more},
    }


@router.get(
    "/pending",
    response_model=StandardResponse[list],
    status_code=status.HTTP_200_OK,
    description="List pending cleaning submissions awaiting supervisor review",
)
async def list_pending_submissions(
    property_id: uuid.UUID,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    cleaning_service: CleaningService = Depends(get_cleaning_service),
):
    verify_tenant(current_user)
    result, total = await cleaning_service.list_pending_submissions(
        property_id, skip, limit
    )
    has_more = (skip + len(result)) < total
    return {
        "success": True,
        "data": result,
        "meta": {"total": total, "skip": skip, "limit": limit, "has_more": has_more},
    }


@router.get(
    "/{submission_id}",
    response_model=StandardResponse[CleaningSubmissionResponse],
    status_code=status.HTTP_200_OK,
    description="Get details of a specific cleaning submission",
)
async def get_submission_detail(
    property_id: uuid.UUID,
    submission_id: uuid.UUID,
    current_user: CurrentHousekeepingStaff,
    cleaning_service: CleaningService = Depends(get_cleaning_service),
):
    verify_tenant(current_user)
    from app.modules.housekeeping_mobile.repositories.task_repository import (
        MobileTaskRepository,
    )

    task_repo = MobileTaskRepository(cleaning_service.db)
    staff = await task_repo.get_staff_by_user_id(current_user.id)
    if not staff:
        return {"success": False, "data": None, "message": "Staff profile not found"}

    result = await cleaning_service.get_submission_detail(
        staff.id, property_id, submission_id
    )
    return {"success": True, "data": result}


@router.patch(
    "/{submission_id}/review",
    response_model=StandardResponse[CleaningSubmissionResponse],
    status_code=status.HTTP_200_OK,
    description="Approve or reject a cleaning submission (supervisor only)",
)
async def review_submission(
    property_id: uuid.UUID,
    submission_id: uuid.UUID,
    payload: SupervisorReviewRequest,
    current_user: CurrentUser,
    cleaning_service: CleaningService = Depends(get_cleaning_service),
):
    verify_tenant(current_user)
    result = await cleaning_service.review_submission(
        supervisor_user_id=current_user.id,
        property_id=property_id,
        submission_id=submission_id,
        status=payload.status,
        rejection_reason=payload.rejection_reason,
    )
    return {"success": True, "data": result}
