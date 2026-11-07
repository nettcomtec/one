"""Seed a 'demo' tenant with a realistic sales pipeline for screenshots/testing."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

os.environ.setdefault("ONE_DATABASE_URL", "postgresql+asyncpg://one:one@127.0.0.1:5432/one_test")
os.environ.setdefault("ONE_REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("ONE_BASE_DOMAIN", "localhost")
os.environ.setdefault("ONE_JWT_SECRET", "demo-secret-at-least-32-bytes-long-xxx")
os.environ.setdefault("ONE_DB_NULL_POOL", "true")

SLUG = "demo"


async def main() -> None:
    from sqlalchemy import text

    from one.crm.models import Activity, ActivityKind, Lead, Partner, PartnerKind, Stage
    from one.crm.service import create_activity, create_lead, ensure_default_pipeline, mark_won
    from one.db.migrate import migrate_public, migrate_tenant
    from one.db.session import engine, schema_for, tenant_session
    from one.identity.service import create_user, has_any_user
    from one.tenancy.provisioning import create_tenant, list_tenant_slugs

    await migrate_public()
    # fresh demo schema
    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_for(SLUG)}" CASCADE'))
        await conn.execute(text("DELETE FROM public.tenant WHERE slug = :s"), {"s": SLUG})
    if SLUG not in await list_tenant_slugs():
        await create_tenant(name="Demo", slug=SLUG)
    await migrate_tenant(SLUG)

    now = datetime.now(UTC)
    async with tenant_session(SLUG) as s:
        if not await has_any_user(s):
            await create_user(
                s, email="alex@demo.com", password="segredo123", full_name="Alex", is_admin=True
            )
        pipe = await ensure_default_pipeline(s)
        stages = {
            st.name: st
            for st in (await s.scalars(__import__("sqlalchemy").select(Stage))).all()
        }

        def partner(name, kind=PartnerKind.company, **kw):
            p = Partner(name=name, kind=kind, **kw)
            s.add(p)
            return p

        p_clinica = partner("Clínica Vida Plena", email="contato@vidaplena.com.br", phone="5541998877665")
        p_loja = partner("Loja Modelo LTDA", email="compras@lojamodelo.com")
        p_auto = partner("Auto Center Zélia", phone="5541991234567")
        p_pad = partner("Padaria do Bairro")
        p_tech = partner("TechSolutions", email="ti@techsolutions.com")
        p_joao = partner("João Mendes", kind=PartnerKind.person, phone="5541987654321")
        p_conta = partner("Contabilidade Nova Era")
        p_escola = partner("Escola Crescer")
        await s.flush()

        async def deal(name, partner, value, stage, prob=None, src="whatsapp",
                       close_days=None, act=None, act_kind=ActivityKind.call,
                       act_in=None, idle_days=None):
            ld = await create_lead(
                s, name=name, partner_id=str(partner.id), value=Decimal(value),
                source=src, stage_id=str(stage.id),
                expected_close_on=(now + timedelta(days=close_days)).date() if close_days else None,
            )
            if prob is not None:
                ld.probability = prob
            if idle_days is not None:
                ld.last_activity_at = now - timedelta(days=idle_days)
            if act:
                a = await create_activity(
                    s, subject=act, kind=act_kind, lead_id=str(ld.id),
                    due_at=(now + timedelta(days=act_in)) if act_in is not None else None,
                )
                _ = a
            return ld

        novo = stages["Novo"]
        qual = stages["Qualificado"]
        prop = stages["Proposta"]
        nego = stages["Negociação"]

        await deal("Plano mensal recorrente", p_clinica, "1890.00", novo,
                   src="whatsapp", act="Ligar para apresentar", act_kind=ActivityKind.call, act_in=0)
        await deal("Troca de PABX para VoIP", p_auto, "3400.00", novo,
                   src="indicação", act="Enviar material", act_kind=ActivityKind.email, act_in=2)
        await deal("Sistema de PDV", p_pad, "890.00", novo, src="site", idle_days=12)

        await deal("Licenças ERP (12 usuários)", p_loja, "7200.00", qual,
                   prob=35, src="whatsapp", close_days=20,
                   act="Reunião de descoberta", act_kind=ActivityKind.meeting, act_in=1)
        await deal("Automação de marketing", p_tech, "4500.00", qual,
                   prob=30, act="Follow-up proposta", act_kind=ActivityKind.call, act_in=-2)

        await deal("Projeto fiscal + financeiro", p_conta, "12800.00", prop,
                   prob=60, src="indicação", close_days=15,
                   act="Enviar contrato", act_kind=ActivityKind.email, act_in=3)
        await deal("Implantação RH", p_escola, "6300.00", prop, prob=65, idle_days=9)

        await deal("Contrato anual Premium", p_joao, "24000.00", nego,
                   prob=85, src="whatsapp", close_days=7,
                   act="Assinatura digital", act_kind=ActivityKind.task, act_in=1)

        # a couple of closed deals so win-rate shows
        won1 = await deal("Setup inicial", p_pad, "1500.00", novo)
        await mark_won(s, lead_id=str(won1.id))

        await s.commit()
    print("seeded demo tenant")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
