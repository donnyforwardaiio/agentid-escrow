import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field

from app.schemas.reputation import ReputationScoreResponse


class CapabilityEnum(str, Enum):
    CODE = "code"
    RESEARCH = "research"
    DATA = "data"
    WRITING = "writing"
    ANALYSIS = "analysis"
    BROWSING = "browsing"
    PLANNING = "planning"
    EXECUTION = "execution"


class AgentRoleEnum(str, Enum):
    consumer = "consumer"
    provider = "provider"


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None)
    owner_email: EmailStr
    capabilities: list[CapabilityEnum] = Field(default=[])
    agent_role: AgentRoleEnum = Field(
        default=AgentRoleEnum.provider,
        description="'provider' = a service agent others can hire. 'consumer' = a personal agent that hires providers.",
    )
    public_key: str = Field(
        ...,
        min_length=64,
        max_length=128,
        description="Ed25519 public key, hex-encoded (64 hex chars = 32 bytes)",
    )


class AgentResponse(BaseModel):
    id: uuid.UUID
    public_key: str
    name: str
    description: str | None
    owner_email: str
    capabilities: list[str]
    agent_role: str
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    reputation: ReputationScoreResponse | None = None

    model_config = {"from_attributes": True}


class AgentPublic(BaseModel):
    """Safe public view — owner_email is omitted."""

    id: uuid.UUID
    public_key: str
    name: str
    description: str | None
    capabilities: list[str]
    agent_role: str
    is_verified: bool
    created_at: datetime
    reputation: ReputationScoreResponse | None = None

    model_config = {"from_attributes": True}
