import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()



database_url = os.environ["DATABASE_URL"]

engine = create_async_engine(
    database_url,
    echo=False,
    # connect_args={"check_same_thread": False},
    # 1. Test connections before checking them out of the pool
    pool_pre_ping=True,
    # 2. Recycle connections older than 5-10 minutes (prevents server-side timeout drops)
    pool_recycle=300,
    # 3. Keep pool size sensible for your host limits (SQLite ignores these)
    # **({} if "sqlite" in database_url else {"pool_size": 10, "max_overflow": 20}),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
