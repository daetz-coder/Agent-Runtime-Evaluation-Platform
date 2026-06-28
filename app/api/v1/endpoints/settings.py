"""
Settings API — runtime configuration endpoints for Agent engineers.

Includes:
  - Prompt template management (list, get, update, create)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.workspace import WorkspaceRole
from app.api.workspace_context import WorkspaceContext, get_workspace_context, require_role

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/settings/prompts")
async def list_prompt_versions(
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """List all available prompt template versions."""
    require_role(ctx, WorkspaceRole.VIEWER)
    from app.agent_runtime.prompts import prompt_manager

    versions = prompt_manager.list_versions()
    return {"versions": versions, "default": "v1.1"}


@router.get("/settings/prompts/{version}")
async def get_prompt(
    version: str,
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Get the full content of a specific prompt version."""
    require_role(ctx, WorkspaceRole.VIEWER)
    from app.agent_runtime.prompts import prompt_manager

    content = prompt_manager.get_prompt(version=version)
    if not content:
        raise HTTPException(status_code=404, detail=f"Prompt version '{version}' not found")

    return {
        "version": version,
        "content": content,
    }


@router.put("/settings/prompts/{version}")
async def update_prompt(
    version: str,
    content: str = Body(..., embed=True),
    description: str = Body("", embed=True),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Create or update a prompt version. Changes take effect immediately."""
    require_role(ctx, WorkspaceRole.ADMIN)
    from app.agent_runtime.prompts import prompt_manager

    path = prompt_manager.save_prompt(version=version, content=content, description=description)
    return {"message": f"Prompt version '{version}' saved", "path": path}
