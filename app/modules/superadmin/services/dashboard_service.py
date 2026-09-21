import time
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.superadmin.repositories.subscription_repository import SubscriptionRepository
from app.modules.auth.models.users_model import User
from app.modules.pms.models.tenants_model import Tenant
from app.modules.booking.models.booking_model import Booking
from app.modules.pms.models.properties_model import Property
from app.modules.superadmin.models.tenant_subscription_model import TenantSubscription
from sqlalchemy import select, func
from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)

# Module-level start time for uptime tracking
_start_time = time.time()


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_health(self) -> dict:
        """Basic system health check."""
        db_status = "ok"
        redis_status = "ok"

        # Check DB
        try:
            await self.db.execute(select(func.count()).select_from(User))
        except Exception as e:
            logger.error(f"[DashboardService] DB health check failed: {e}")
            db_status = "error"

        # Check Redis
        try:
            from app.config.redis_config import redis_pool
            import redis.asyncio as aioredis

            async with aioredis.Redis(connection_pool=redis_pool) as client:
                await client.ping()
        except Exception as e:
            logger.error(f"[DashboardService] Redis health check failed: {e}")
            redis_status = "error"

        overall_status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

        # Counts
        try:
            result = await self.db.execute(select(func.count()).select_from(User))
            total_users = result.scalar_one() or 0

            result = await self.db.execute(select(func.count()).select_from(Tenant))
            total_tenants = result.scalar_one() or 0

            result = await self.db.execute(select(func.count()).select_from(Booking))
            total_bookings = result.scalar_one() or 0

            result = await self.db.execute(
                select(func.count())
                .select_from(TenantSubscription)
                .where(TenantSubscription.status == "ACTIVE")
            )
            active_subscriptions = result.scalar_one() or 0
        except Exception:
            total_users = 0
            total_tenants = 0
            total_bookings = 0
            active_subscriptions = 0

        return {
            "status": overall_status,
            "db_status": db_status,
            "redis_status": redis_status,
            "uptime_seconds": round(time.time() - _start_time, 2),
            "total_users": total_users,
            "total_tenants": total_tenants,
            "total_bookings": total_bookings,
            "active_subscriptions": active_subscriptions,
        }
