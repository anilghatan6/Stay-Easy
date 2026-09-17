from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.config.database_config import get_db
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.service import DashboardService


def get_dashboard_service(
    db: AsyncSession = Depends(get_db),
) -> DashboardService:
    dashboard_repo = DashboardRepository(db)
    return DashboardService(
        db=db,
        dashboard_repo=dashboard_repo,
    )
