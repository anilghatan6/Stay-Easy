from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database_config import get_db
from app.modules.subscription.enforcement_service import PlanEnforcementService


async def get_plan_enforcement(
    db: AsyncSession = Depends(get_db),
) -> PlanEnforcementService:
    return PlanEnforcementService(db)
