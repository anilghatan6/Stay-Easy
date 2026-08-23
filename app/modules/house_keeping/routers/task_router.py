
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.house_keeping.schemas.task_schema import CreateTaskRequest, UpdateTaskRequest, TaskResponse
from app.modules.house_keeping.models.task_model import TaskStatus
from app.modules.house_keeping.services.task_service import TaskService
from app.middlewares.auth_middlewares import CurrentUser
from app.modules.house_keeping.dependencies import get_task_service
from app.utils.schemas import StandardResponse

router = APIRouter(prefix="/properties/{property_id}/tasks", tags=["housekeeping-tasks"])

@router.post("", response_model=StandardResponse[TaskResponse], status_code=status.HTTP_201_CREATED)
async def create_task(
    property_id: uuid.UUID,
    payload: CreateTaskRequest,
    current_user: CurrentUser,  # Admin/Manager
    task_service: TaskService = Depends(get_task_service),
):
    result = await task_service.create_task(property_id, current_user.id, payload)
    return {
        "success": True,
        "data": result
    }
  
