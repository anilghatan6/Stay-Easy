from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database_config import get_db
from app.modules.auth.services.auth_services import AuthService
from app.modules.superadmin.repositories.admin_repository import AdminRepository
from app.modules.superadmin.repositories.audit_repository import AuditRepository
from app.modules.superadmin.repositories.subscription_repository import SubscriptionRepository
from app.modules.superadmin.repositories.feature_flag_repository import FeatureFlagRepository
from app.modules.superadmin.repositories.announcement_repository import AnnouncementRepository
from app.modules.superadmin.services.admin_service import AdminService
from app.modules.superadmin.services.audit_service import AuditService
from app.modules.superadmin.services.subscription_service import SubscriptionService
from app.modules.superadmin.services.feature_flag_service import FeatureFlagService
from app.modules.superadmin.services.announcement_service import AnnouncementService
from app.modules.superadmin.services.dashboard_service import DashboardService


def get_auth_service() -> AuthService:
    return AuthService()


def get_admin_repository(db: AsyncSession = Depends(get_db)) -> AdminRepository:
    return AdminRepository(db)


def get_audit_repository(db: AsyncSession = Depends(get_db)) -> AuditRepository:
    return AuditRepository(db)


def get_subscription_repository(db: AsyncSession = Depends(get_db)) -> SubscriptionRepository:
    return SubscriptionRepository(db)


def get_feature_flag_repository(db: AsyncSession = Depends(get_db)) -> FeatureFlagRepository:
    return FeatureFlagRepository(db)


def get_announcement_repository(db: AsyncSession = Depends(get_db)) -> AnnouncementRepository:
    return AnnouncementRepository(db)


def get_audit_service(
    audit_repo: AuditRepository = Depends(get_audit_repository),
) -> AuditService:
    return AuditService(audit_repo=audit_repo)


def get_admin_service(
    db: AsyncSession = Depends(get_db),
    admin_repo: AdminRepository = Depends(get_admin_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> AdminService:
    return AdminService(
        db=db,
        admin_repo=admin_repo,
        audit_repo=audit_repo,
        auth_service=auth_service,
    )


def get_subscription_service(
    db: AsyncSession = Depends(get_db),
    subscription_repo: SubscriptionRepository = Depends(get_subscription_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> SubscriptionService:
    return SubscriptionService(
        db=db,
        subscription_repo=subscription_repo,
        audit_repo=audit_repo,
        auth_service=auth_service,
    )


def get_feature_flag_service(
    db: AsyncSession = Depends(get_db),
    feature_flag_repo: FeatureFlagRepository = Depends(get_feature_flag_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
) -> FeatureFlagService:
    return FeatureFlagService(
        db=db,
        feature_flag_repo=feature_flag_repo,
        audit_repo=audit_repo,
    )


def get_announcement_service(
    db: AsyncSession = Depends(get_db),
    announcement_repo: AnnouncementRepository = Depends(get_announcement_repository),
    audit_repo: AuditRepository = Depends(get_audit_repository),
) -> AnnouncementService:
    return AnnouncementService(
        db=db,
        announcement_repo=announcement_repo,
        audit_repo=audit_repo,
    )


def get_dashboard_service(
    db: AsyncSession = Depends(get_db),
) -> DashboardService:
    return DashboardService(db=db)
