"""
Database configuration and session management.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine
_engine_kwargs: dict = {
    "echo": settings.SQL_ECHO,
    "pool_pre_ping": True,
}
if "sqlite" in settings.DATABASE_URL:
    # SQLite (especially aiosqlite) does not benefit from a large connection pool.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs,
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
    """Initialize database by running Alembic migrations to head."""
    # Register all ORM models so metadata is populated
    from app.api.workspace import AuditLog, Workspace, WorkspaceMember  # noqa: F401
    from app.db.models import AgentTask, AgentTrajectory, Evaluation  # noqa: F401

    await _run_alembic_upgrade()


async def _run_alembic_upgrade() -> None:
    """Run database schema initialization.

    For SQLite (development), use create_all directly to avoid
    alembic async event-loop conflicts.
    For PostgreSQL (production), attempt alembic upgrade first.
    """
    is_sqlite = "sqlite" in settings.DATABASE_URL

    if is_sqlite:
        # SQLite dev mode: use create_all directly
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created via create_all (SQLite dev mode)")
        return

    # PostgreSQL production mode: run alembic migrations
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    try:
        script = ScriptDirectory.from_config(alembic_cfg)
        head = script.get_current_head()

        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully (head: %s)", head)
    except Exception as e:
        logger.warning("Alembic migration failed, falling back to create_all: %s", e)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
