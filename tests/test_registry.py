"""Tool registry: registration, permission gating, typed validation."""
import pytest
from pydantic import BaseModel

from one.ai.registry import (
    PermissionDenied,
    Tool,
    ToolContext,
    ToolRegistry,
)


class EchoIn(BaseModel):
    value: str


async def _echo(ctx: ToolContext, args: EchoIn) -> dict:
    return {"echo": args.value, "by": ctx.user_id}


def _registry_with_echo(permission=None) -> ToolRegistry:
    r = ToolRegistry()
    r.register(
        Tool(
            name="demo.echo",
            description="echo",
            args_model=EchoIn,
            handler=_echo,
            permission=permission,
        )
    )
    return r


def test_schemas_expose_input_model():
    r = _registry_with_echo()
    schemas = r.json_schemas()
    assert schemas[0]["name"] == "demo.echo"
    assert "value" in schemas[0]["input_schema"]["properties"]


async def test_execute_runs_handler():
    r = _registry_with_echo()
    ctx = ToolContext(session=None, tenant="t", user_id="u1", permissions={"*"})
    out = await r.execute("demo.echo", {"value": "hi"}, ctx)
    assert out == {"echo": "hi", "by": "u1"}


async def test_permission_denied():
    r = _registry_with_echo(permission="demo.use")
    ctx = ToolContext(session=None, tenant="t", user_id="u1", permissions=set())
    with pytest.raises(PermissionDenied):
        await r.execute("demo.echo", {"value": "hi"}, ctx)


async def test_admin_wildcard_allows():
    r = _registry_with_echo(permission="demo.use")
    ctx = ToolContext(session=None, tenant="t", user_id="u1", permissions={"*"})
    out = await r.execute("demo.echo", {"value": "ok"}, ctx)
    assert out["echo"] == "ok"


async def test_unknown_tool_raises():
    r = _registry_with_echo()
    ctx = ToolContext(session=None, tenant="t", permissions={"*"})
    with pytest.raises(KeyError):
        await r.execute("nope", {}, ctx)
