"""escrow schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums only if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE escrow_status AS ENUM (
                'pending', 'funded', 'completed', 'disputed', 'refunded', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE dispute_status AS ENUM (
                'open', 'resolved_payer', 'resolved_payee'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # escrow_transactions table
    op.execute("""
        CREATE TABLE IF NOT EXISTS escrow_transactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            payer_agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
            payee_agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
            amount NUMERIC(18, 2) NOT NULL,
            fee_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
            currency VARCHAR(3) NOT NULL DEFAULT 'USD',
            status escrow_status NOT NULL DEFAULT 'pending',
            task_description TEXT NOT NULL,
            stripe_payment_intent_id VARCHAR(255) UNIQUE,
            release_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_escrow_transactions_id ON escrow_transactions(id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_escrow_transactions_payer ON escrow_transactions(payer_agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_escrow_transactions_payee ON escrow_transactions(payee_agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_escrow_transactions_status ON escrow_transactions(status);")

    # disputes table
    op.execute("""
        CREATE TABLE IF NOT EXISTS disputes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            transaction_id UUID NOT NULL UNIQUE REFERENCES escrow_transactions(id) ON DELETE CASCADE,
            opened_by_agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
            reason TEXT NOT NULL,
            status dispute_status NOT NULL DEFAULT 'open',
            resolution_notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_disputes_id ON disputes(id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_disputes_transaction_id ON disputes(transaction_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS disputes;")
    op.execute("DROP TABLE IF EXISTS escrow_transactions;")
    op.execute("DROP TYPE IF EXISTS dispute_status;")
    op.execute("DROP TYPE IF EXISTS escrow_status;")
