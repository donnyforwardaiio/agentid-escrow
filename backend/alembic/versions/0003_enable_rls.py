"""Enable RLS on all public tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-19

Enables Row Level Security on every table in the public schema.
The FastAPI backend connects via the postgres/service role and bypasses
RLS automatically, so no application behaviour changes.
PostgREST (anon/authenticated roles) will be denied by default — no
explicit policy = deny all, which is correct for this architecture.

alembic_version is an internal Alembic table and should never be
accessible via the PostgREST API.
"""
from alembic import op

revision: str = "0003"
down_revision: str = "0002"
branch_labels = None
depends_on = None

TABLES = [
    "alembic_version",
    "agents",
    "reputation_events",
    "reputation_scores",
    "audit_log",
    "escrow_transactions",
    "disputes",
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
        # Force RLS even for table owners (belt-and-braces).
        # The service_role in Supabase bypasses RLS regardless, so this
        # only affects direct owner connections that aren't superusers.
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY;")
