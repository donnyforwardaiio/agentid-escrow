import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class EscrowStatus(str, enum.Enum):
    PENDING = "pending"           # created, awaiting payment
    FUNDED = "funded"             # payment confirmed, funds locked
    COMPLETED = "completed"       # task done, funds released to payee
    DISPUTED = "disputed"         # dispute opened
    REFUNDED = "refunded"         # funds returned to payer
    CANCELLED = "cancelled"       # cancelled before funding


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED_PAYER = "resolved_payer"     # resolved in payer's favour
    RESOLVED_PAYEE = "resolved_payee"     # resolved in payee's favour


class EscrowTransaction(Base):
    __tablename__ = "escrow_transactions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    payer_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payee_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    fee_amount = Column(Numeric(precision=18, scale=2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(
        Enum(EscrowStatus, name="escrow_status"),
        nullable=False,
        default=EscrowStatus.PENDING,
        index=True,
    )
    task_description = Column(Text, nullable=False)
    stripe_payment_intent_id = Column(String(255), nullable=True, unique=True)
    release_at = Column(DateTime(timezone=True), nullable=True)  # auto-release time
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    payer = relationship("Agent", foreign_keys=[payer_agent_id])
    payee = relationship("Agent", foreign_keys=[payee_agent_id])
    dispute = relationship("Dispute", back_populates="transaction", uselist=False)


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("escrow_transactions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    opened_by_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason = Column(Text, nullable=False)
    status = Column(
        Enum(DisputeStatus, name="dispute_status"),
        nullable=False,
        default=DisputeStatus.OPEN,
    )
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    transaction = relationship("EscrowTransaction", back_populates="dispute")
    opened_by = relationship("Agent", foreign_keys=[opened_by_agent_id])
