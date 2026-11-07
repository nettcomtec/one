"""Ledger actions exposed as AI tools. Importing this module registers them."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from one.ai.events import Event, bus
from one.ai.registry import ToolContext, tool
from one.ledger.service import LineInput, post_move


class PostMoveLineIn(BaseModel):
    account_id: str
    debit: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit: Decimal = Field(default=Decimal("0.00"), ge=0)
    label: str | None = None


class PostMoveIn(BaseModel):
    journal_id: str
    ref: str | None = None
    lines: list[PostMoveLineIn] = Field(min_length=2)


@tool(
    "ledger.post_move",
    permission="ledger.post",
    description="Post a balanced double-entry accounting move (debits must equal credits).",
)
async def post_move_tool(ctx: ToolContext, args: PostMoveIn) -> dict:
    move = await post_move(
        ctx.session,
        journal_id=args.journal_id,
        ref=args.ref,
        actor=ctx.user_id,
        lines=[
            LineInput(account_id=ln.account_id, debit=ln.debit, credit=ln.credit, label=ln.label)
            for ln in args.lines
        ],
    )
    await bus.publish(
        Event(name="ledger.move.posted", tenant=ctx.tenant, payload={"move_id": str(move.id)})
    )
    return {"id": str(move.id), "name": move.name, "state": move.state.value}
