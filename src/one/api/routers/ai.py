"""Expose the AI tool registry: list tools (for an LLM/agent) and execute one.

This is the bridge an MCP server or function-calling loop talks to. The same
permission check the UI uses applies here, so an agent is just another caller.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from one.ai.registry import PermissionDenied, ToolContext, registry
from one.api.deps import current_principal, db_session
from one.identity.security import Principal

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/tools")
async def list_tools() -> list[dict]:
    return registry.json_schemas()


class ExecuteIn(BaseModel):
    tool: str
    args: dict = {}


@router.post("/execute")
async def execute_tool(
    body: ExecuteIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(db_session),
) -> dict:
    ctx = ToolContext(
        session=session,
        tenant=principal.tenant,
        user_id=principal.user_id,
        permissions={"*"} if principal.is_admin else set(),
    )
    try:
        result = await registry.execute(body.tool, body.args, ctx)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"result": result}
