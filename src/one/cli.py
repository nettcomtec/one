"""Small operational CLI (tenant provisioning, dev token issuing).

python -m one.cli create-tenant --name "Cliente X" --slug cliente_x
python -m one.cli migrate
python -m one.cli issue-token --tenant cliente_x --user <uuid> --admin
"""

from __future__ import annotations

import argparse
import asyncio

from one.db.migrate import migrate_all, migrate_tenant
from one.identity.security import Principal, issue_token
from one.tenancy.provisioning import create_tenant


async def _create_tenant(args) -> None:
    info = await create_tenant(name=args.name, slug=args.slug, cnpj=args.cnpj)
    await migrate_tenant(info["slug"])
    print(f"Created tenant {info['slug']} (schema {info['schema']})")


def _issue_token(args) -> None:
    token = issue_token(
        Principal(user_id=args.user, tenant=args.tenant, email=args.email, is_admin=args.admin)
    )
    print(token)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="one")
    sub = p.add_subparsers(dest="cmd", required=True)

    ct = sub.add_parser("create-tenant")
    ct.add_argument("--name", required=True)
    ct.add_argument("--slug")
    ct.add_argument("--cnpj")
    ct.set_defaults(func=lambda a: asyncio.run(_create_tenant(a)))

    mg = sub.add_parser("migrate")
    mg.set_defaults(func=lambda a: asyncio.run(migrate_all()))

    it = sub.add_parser("issue-token")
    it.add_argument("--tenant", required=True)
    it.add_argument("--user", required=True)
    it.add_argument("--email")
    it.add_argument("--admin", action="store_true")
    it.set_defaults(func=_issue_token)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
