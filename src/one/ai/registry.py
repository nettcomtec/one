"""AI tool registry — the heart of "AI-native".

Every domain action a human can take is also registered as a typed tool. An
agent (via MCP, function-calling, or the voice bot) sees exactly the same
surface the UI uses, with the same permission check, so it cannot do anything a
user with those permissions couldn't. Each tool declares a pydantic input
model, a required permission code, and an async handler.

Registering:

    class CreateLeadIn(BaseModel):
        name: str
        phone: str

    @tool("crm.create_lead", permission="crm.lead.create",
          description="Create a CRM lead")
    async def create_lead(ctx: ToolContext, args: CreateLeadIn) -> dict:
        ...

Exposing to an LLM:  ``registry.openai_schema()`` / ``registry.list()``
Executing:           ``await registry.execute(name, raw_args, ctx)``
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar, get_type_hints

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

TArgs = TypeVar("TArgs", bound=BaseModel)


@dataclass
class ToolContext:
    """What a tool handler gets: the tenant-scoped session and the caller."""

    session: AsyncSession
    tenant: str
    user_id: str | None = None
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str | None) -> bool:
        if permission is None:
            return True
        return "*" in self.permissions or permission in self.permissions


@dataclass
class Tool(Generic[TArgs]):
    name: str
    description: str
    args_model: type[TArgs]
    handler: Callable[[ToolContext, TArgs], Awaitable[Any]]
    permission: str | None = None

    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.args_model.model_json_schema(),
        }


class PermissionDenied(PermissionError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def json_schemas(self) -> list[dict]:
        return [t.json_schema() for t in self._tools.values()]

    async def execute(self, name: str, raw_args: dict, ctx: ToolContext) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool '{name}'")
        if not ctx.can(tool.permission):
            raise PermissionDenied(f"Missing permission '{tool.permission}' for '{name}'")
        args = tool.args_model.model_validate(raw_args)
        return await tool.handler(ctx, args)


# Process-wide registry. Modules register their tools at import time.
registry = ToolRegistry()


def tool(
    name: str,
    *,
    permission: str | None = None,
    description: str = "",
):
    """Decorator registering an async ``(ctx, args)`` handler as a tool.

    The args model is read from the handler's second parameter annotation.
    """

    def decorator(func: Callable[[ToolContext, TArgs], Awaitable[Any]]):
        # Resolve string annotations (PEP 563) to real types, then take the
        # second positional parameter's type as the args model.
        hints = get_type_hints(func)
        param_names = list(inspect.signature(func).parameters)
        args_model = hints.get(param_names[1]) if len(param_names) >= 2 else None
        if not (isinstance(args_model, type) and issubclass(args_model, BaseModel)):
            raise TypeError(f"Tool '{name}' handler must annotate its args param with a BaseModel")
        registry.register(
            Tool(
                name=name,
                description=description or (func.__doc__ or "").strip(),
                args_model=args_model,
                handler=func,
                permission=permission,
            )
        )
        return func

    return decorator
