import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL must be configured")
    return value.replace("postgresql://", "postgresql+asyncpg://", 1) if value.startswith("postgresql://") else value


engine = create_async_engine(database_url(), pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session():
    async with SessionFactory() as session:
        yield session
