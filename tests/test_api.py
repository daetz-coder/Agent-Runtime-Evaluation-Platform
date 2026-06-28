"""
Tests for API endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient

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
    assert data["status"] in ("healthy", "degraded")
    assert "app" in data
    assert "database" in data
    assert "wiki" in data


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
async def test_create_task_idempotent(client):
    """Client-provided task id must not create duplicates on retry."""
    task_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    payload = {
        "id": task_id,
        "goal": "Idempotent wiki-agent task",
        "context": {"agent": "wiki-agent"},
    }
    first = await client.post("/api/v1/tasks/", json=payload)
    second = await client.post("/api/v1/tasks/", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == task_id
    assert second.json()["id"] == task_id

    listed = await client.get("/api/v1/tasks/")
    matches = [t for t in listed.json() if t["id"] == task_id]
    assert len(matches) == 1


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
async def test_monotonicity_benchmark_metadata(client):
    """Benchmark metadata endpoint is registered and returns reference curve."""
    response = await client.get("/api/v1/benchmark/monotonicity")
    assert response.status_code == 200
    data = response.json()
    assert "quality_order" in data
    assert len(data["quality_order"]) == 6
    assert "reference_scores" in data
    assert data["reference_scores"][0]["overall"] == 93.1


@pytest.mark.asyncio
async def test_evaluation_summary(client):
    """Test evaluation summary endpoint."""
    response = await client.get("/api/v1/reports/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_evaluations" in data
    assert "average_scores" in data


@pytest.mark.asyncio
async def test_auth_middleware_returns_401(client):
    """Auth middleware must return 401 JSON, not 500, when enabled."""
    from app.core.config import settings

    prev_enabled = settings.AUTH_ENABLED
    prev_key = settings.API_KEY
    try:
        settings.AUTH_ENABLED = True
        settings.API_KEY = "test-api-key"
        response = await client.get("/api/v1/tasks/")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or missing API key"
    finally:
        settings.AUTH_ENABLED = prev_enabled
        settings.API_KEY = prev_key
