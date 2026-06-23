"""
Database configuration and session management.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency for getting async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables and apply lightweight schema patches."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_schema_patches)


def _apply_schema_patches(connection) -> None:
    """Add columns introduced after initial deploy (SQLite has no ALTER IF NOT EXISTS)."""
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    if "evaluations" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("evaluations")}
    if "stream_mode" not in columns:
        connection.execute(text("ALTER TABLE evaluations ADD COLUMN stream_mode BOOLEAN DEFAULT 0 NOT NULL"))


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
