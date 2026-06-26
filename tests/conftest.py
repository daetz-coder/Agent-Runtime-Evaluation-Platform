"""Pytest fixtures for database initialization."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure tables exist and schema patches are applied before API tests."""
    import asyncio

    from app.db.database import init_db

    asyncio.run(init_db())
