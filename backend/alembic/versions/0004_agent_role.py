"""Add agent_role column to agents table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-19

Adds agent_role to distinguish consumer agents (personal AI assistants)
from provider agents (services that other agents can hire).
"""
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: str = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE agent_role AS ENUM ('consumer', 'provider');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        ALTER TABLE public.agents
        ADD COLUMN IF NOT EXISTS agent_role agent_role NOT NULL DEFAULT 'provider';
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agents_role ON public.agents(agent_role);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agents_role;")
    op.execute("ALTER TABLE public.agents DROP COLUMN IF EXISTS agent_role;")
    op.execute("DROP TYPE IF EXISTS agent_role;")
