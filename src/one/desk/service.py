"""Help Desk service — create/update tickets, with SLA bookkeeping."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from one.comms.service import now_ms
from one.desk.models import SlaState, Ticket, TicketPriority, TicketStatus
from one.sequences.service import next_number

_SLA_MIN = {
    TicketPriority.low: 480,
    TicketPriority.normal: 120,
    TicketPriority.high: 60,
    TicketPriority.urgent: 15,
}


async def create_ticket(
    session: AsyncSession,
    *,
    subject: str,
    partner_id: str | None = None,
    conversation_id: str | None = None,
    priority: TicketPriority = TicketPriority.normal,
    description: str | None = None,
) -> Ticket:
    due = now_ms() + _SLA_MIN[priority] * 60 * 1000
    ticket = Ticket(
        subject=subject,
        description=description,
        partner_id=uuid.UUID(partner_id) if partner_id else None,
        conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
        priority=priority,
        status=TicketStatus.open,
        sla_state=SlaState.running,
        sla_due_at=due,
    )
    session.add(ticket)
    await session.flush()
    ticket.number = await next_number(session, code="desk.ticket")
    await session.flush()
    return ticket


async def set_status(session: AsyncSession, *, ticket_id: str, status: TicketStatus) -> Ticket:
    ticket = await session.get(Ticket, uuid.UUID(ticket_id))
    if ticket is None:
        raise ValueError("Ticket não encontrado")
    ticket.status = status
    if status in (TicketStatus.resolved, TicketStatus.closed):
        ticket.sla_state = SlaState.met
    elif status == TicketStatus.on_hold:
        ticket.sla_state = SlaState.paused
    await session.flush()
    return ticket
