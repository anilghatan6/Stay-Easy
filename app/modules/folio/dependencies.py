from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.config.database_config import get_db
from app.modules.folio.repository import FolioRepository
from app.modules.folio.service import FolioService


def get_folio_service(
    db: AsyncSession = Depends(get_db),
) -> FolioService:
    folio_repo = FolioRepository(db)
    return FolioService(
        db=db,
        folio_repo=folio_repo,
    )
