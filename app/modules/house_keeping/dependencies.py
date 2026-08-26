from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database_config import get_db
from app.modules.house_keeping.repositories.task_repository import TaskRepository
from app.modules.house_keeping.services.task_service import TaskService
from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.modules.staff_mgmt.repositories.staffs_repository import StaffRepository


def get_task_repository(db: AsyncSession = Depends(get_db)) -> TaskRepository:
    return TaskRepository(db)


def get_property_repository(db: AsyncSession = Depends(get_db)) -> PropertyRepository:
    return PropertyRepository(db)


def get_room_repository(db: AsyncSession = Depends(get_db)) -> RoomRepository:
    return RoomRepository(db)


def get_staff_repository(db: AsyncSession = Depends(get_db)) -> StaffRepository:
    return StaffRepository(db)


def get_task_service(
    db: AsyncSession = Depends(get_db),
    task_repo: TaskRepository = Depends(get_task_repository),
    prop_repo: PropertyRepository = Depends(get_property_repository),
    room_repo: RoomRepository = Depends(get_room_repository),
    staff_repo: StaffRepository = Depends(get_staff_repository),
) -> TaskService:
    return TaskService(
        db=db,
        task_repo=task_repo,
        prop_repo=prop_repo,
        room_repo=room_repo,
        staff_repo=staff_repo,
    )
