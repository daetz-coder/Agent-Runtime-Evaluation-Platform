"""Multi-tenant workspace isolation and RBAC tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def auth_settings():
    """Enable auth with stable keys for the test session."""
    prev = {
        "AUTH_ENABLED": settings.AUTH_ENABLED,
        "API_KEY": settings.API_KEY,
        "SECRET_KEY": settings.SECRET_KEY,
    }
    settings.AUTH_ENABLED = True
    settings.API_KEY = "test-global-admin-key"
    settings.SECRET_KEY = "test-global-admin-key"
    yield settings
    settings.AUTH_ENABLED = prev["AUTH_ENABLED"]
    settings.API_KEY = prev["API_KEY"]
    settings.SECRET_KEY = prev["SECRET_KEY"]


def admin_headers() -> dict:
    return {"Authorization": "Bearer test-global-admin-key"}


@pytest.mark.asyncio
async def test_workspace_task_isolation(client, auth_settings):
    """Tasks created under one workspace must not be visible to another."""
    ws_a = await client.post(
        "/api/v1/workspaces/",
        json={"name": "Tenant A", "description": "test"},
        headers=admin_headers(),
    )
    assert ws_a.status_code == 201
    key_a = ws_a.json()["api_key"]

    ws_b = await client.post(
        "/api/v1/workspaces/",
        json={"name": "Tenant B", "description": "test"},
        headers=admin_headers(),
    )
    assert ws_b.status_code == 201
    key_b = ws_b.json()["api_key"]

    task_resp = await client.post(
        "/api/v1/tasks/",
        json={"goal": "Tenant A task"},
        headers={"Authorization": f"Bearer {key_a}"},
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]
    assert task_resp.json()["workspace_id"] == ws_a.json()["id"]

    cross_get = await client.get(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {key_b}"},
    )
    assert cross_get.status_code == 404

    history = await client.get(
        f"/api/v1/reports/tasks/{task_id}/history",
        headers={"Authorization": f"Bearer {key_b}"},
    )
    assert history.status_code == 404


@pytest.mark.asyncio
async def test_viewer_cannot_delete_task(client, auth_settings):
    """Viewer role must receive 403 on destructive operations."""
    ws = await client.post(
        "/api/v1/workspaces/",
        json={"name": "RBAC WS"},
        headers=admin_headers(),
    )
    ws_id = ws.json()["id"]
    api_key = ws.json()["api_key"]

    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"user_id": "viewer-1", "role": "viewer"},
        headers=admin_headers(),
    )

    task_resp = await client.post(
        "/api/v1/tasks/",
        json={"goal": "RBAC task"},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    task_id = task_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/v1/tasks/{task_id}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-User-Id": "viewer-1",
        },
    )
    assert delete_resp.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_assigns_workspace_via_header(client, auth_settings):
    """Super admin can assign workspace_id via X-Workspace-Id header."""
    ws = await client.post(
        "/api/v1/workspaces/",
        json={"name": "Header WS"},
        headers=admin_headers(),
    )
    ws_id = ws.json()["id"]

    task_resp = await client.post(
        "/api/v1/tasks/",
        json={"goal": "Scoped by header"},
        headers={**admin_headers(), "X-Workspace-Id": ws_id},
    )
    assert task_resp.status_code == 201
    assert task_resp.json()["workspace_id"] == ws_id
