import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReputationEventType(str, Enum):
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    DISPUTE_RAISED = "DISPUTE_RAISED"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED"
    VERIFICATION_PASSED = "VERIFICATION_PASSED"


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counterparty_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    score_delta: Mapped[float] = mapped_column(Float, nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ReputationEvent id={self.id} type={self.event_type} delta={self.score_delta}>"


class ReputationScore(Base):
    __tablename__ = "reputation_scores"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    overall_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    completion_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    accuracy_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    dispute_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ReputationScore agent_id={self.agent_id} score={self.overall_score}>"
