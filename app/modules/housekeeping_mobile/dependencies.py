from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database_config import get_db
from app.modules.housekeeping_mobile.repositories.task_repository import MobileTaskRepository
from app.modules.housekeeping_mobile.repositories.schedule_repository import ScheduleRepository
from app.modules.housekeeping_mobile.repositories.maintenance_repository import MaintenanceRepository
from app.modules.housekeeping_mobile.repositories.history_repository import HistoryRepository
from app.modules.housekeeping_mobile.repositories.cleaning_repository import CleaningRepository
from app.modules.housekeeping_mobile.services.task_service import MobileTaskService
from app.modules.housekeeping_mobile.services.schedule_service import ScheduleService
from app.modules.housekeeping_mobile.services.maintenance_service import MaintenanceService
from app.modules.housekeeping_mobile.services.history_service import HistoryService
from app.modules.housekeeping_mobile.services.cleaning_service import CleaningService
from app.modules.pms.repositories.room_repo import RoomRepository
from app.Images.image_services import ImageService


def get_mobile_task_repository(db: AsyncSession = Depends(get_db)) -> MobileTaskRepository:
    return MobileTaskRepository(db)


def get_schedule_repository(db: AsyncSession = Depends(get_db)) -> ScheduleRepository:
    return ScheduleRepository(db)


def get_maintenance_repository(db: AsyncSession = Depends(get_db)) -> MaintenanceRepository:
    return MaintenanceRepository(db)


def get_history_repository(db: AsyncSession = Depends(get_db)) -> HistoryRepository:
    return HistoryRepository(db)


def get_mobile_room_repository(db: AsyncSession = Depends(get_db)) -> RoomRepository:
    return RoomRepository(db)


def get_mobile_image_service() -> ImageService:
    return ImageService()


def get_mobile_task_service(
    db: AsyncSession = Depends(get_db),
    task_repo: MobileTaskRepository = Depends(get_mobile_task_repository),
) -> MobileTaskService:
    return MobileTaskService(db=db, task_repo=task_repo)


def get_schedule_service(
    db: AsyncSession = Depends(get_db),
    schedule_repo: ScheduleRepository = Depends(get_schedule_repository),
    task_repo: MobileTaskRepository = Depends(get_mobile_task_repository),
) -> ScheduleService:
    return ScheduleService(db=db, schedule_repo=schedule_repo, task_repo=task_repo)


def get_maintenance_service(
    db: AsyncSession = Depends(get_db),
    maintenance_repo: MaintenanceRepository = Depends(get_maintenance_repository),
    room_repo: RoomRepository = Depends(get_mobile_room_repository),
    image_service: ImageService = Depends(get_mobile_image_service),
) -> MaintenanceService:
    return MaintenanceService(
        db=db,
        maintenance_repo=maintenance_repo,
        room_repo=room_repo,
        image_service=image_service,
    )


def get_history_service(
    db: AsyncSession = Depends(get_db),
    history_repo: HistoryRepository = Depends(get_history_repository),
) -> HistoryService:
    return HistoryService(db=db, history_repo=history_repo)


def get_cleaning_repository(db: AsyncSession = Depends(get_db)) -> CleaningRepository:
    return CleaningRepository(db)


def get_cleaning_service(
    db: AsyncSession = Depends(get_db),
    cleaning_repo: CleaningRepository = Depends(get_cleaning_repository),
    task_repo: MobileTaskRepository = Depends(get_mobile_task_repository),
    room_repo: RoomRepository = Depends(get_mobile_room_repository),
    image_service: ImageService = Depends(get_mobile_image_service),
) -> CleaningService:
    return CleaningService(
        db=db,
        cleaning_repo=cleaning_repo,
        task_repo=task_repo,
        room_repo=room_repo,
        image_service=image_service,
    )
