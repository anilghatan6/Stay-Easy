from app.modules.house_keeping.repositories.task_repository import TaskRepository
from app.modules.house_keeping.services.task_service import TaskService
from fastapi import Depends


def get_task_repository() -> TaskRepository:
    return TaskRepository()


def get_task_service(task_repo: TaskRepository = Depends(get_task_repository)) -> TaskService:
    return TaskService(task_repo)