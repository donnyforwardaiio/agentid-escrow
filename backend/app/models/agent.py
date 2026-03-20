import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, Uuid, func
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

import enum


class AgentRole(str, enum.Enum):
    consumer = "consumer"
    provider = "provider"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    public_key: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    # JSON works on both SQLite (tests) and PostgreSQL (production)
    capabilities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    agent_role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, name="agent_role", create_constraint=True),
        nullable=False,
        default=AgentRole.provider,
        index=True,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r}>"
