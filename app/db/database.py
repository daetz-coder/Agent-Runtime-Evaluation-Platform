"""
Database configuration and session management.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


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
    """Initialize database tables and apply lightweight schema patches."""
    # 注册所有 ORM 模型（含 workspace 表）
    from app.db.models import AgentTask, AgentTrajectory, Evaluation  # noqa: F401
    from app.api.workspace import Workspace, WorkspaceMember, AuditLog  # noqa: F401

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

    if "agent_tasks" in inspector.get_table_names():
        task_columns = {col["name"] for col in inspector.get_columns("agent_tasks")}
        if "workspace_id" not in task_columns:
            connection.execute(text("ALTER TABLE agent_tasks ADD COLUMN workspace_id VARCHAR(36)"))


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
