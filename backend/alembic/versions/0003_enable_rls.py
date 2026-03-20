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
        # IF EXISTS guards against tables not yet created (e.g. escrow tables on Phase-1-only DBs)
        op.execute(f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables
                           WHERE table_schema = 'public' AND table_name = '{table}') THEN
                    EXECUTE 'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY';
                    EXECUTE 'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY';
                END IF;
            END $$;
        """)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables
                           WHERE table_schema = 'public' AND table_name = '{table}') THEN
                    EXECUTE 'ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY';
                    EXECUTE 'ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY';
                END IF;
            END $$;
        """)
