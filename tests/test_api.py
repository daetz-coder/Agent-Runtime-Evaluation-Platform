"""
Tests for API endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health_check(client):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data


@pytest.mark.asyncio
async def test_root(client):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_create_task(client):
    """Test task creation."""
    task_data = {
        "goal": "Fix authentication bug",
        "context": {"project": "web-app"},
    }
    response = await client.post("/api/v1/tasks/", json=task_data)
    assert response.status_code == 201
    data = response.json()
    assert data["goal"] == task_data["goal"]
    assert "id" in data


@pytest.mark.asyncio
async def test_list_tasks(client):
    """Test task listing."""
    response = await client.get("/api/v1/tasks/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_task_not_found(client):
    """Test getting non-existent task."""
    response = await client.get("/api/v1/tasks/non-existent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_evaluation_summary(client):
    """Test evaluation summary endpoint."""
    response = await client.get("/api/v1/reports/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_evaluations" in data
    assert "average_scores" in data
