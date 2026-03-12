import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.reputation import ReputationEventType


class ReputationScoreResponse(BaseModel):
    agent_id: uuid.UUID
    overall_score: float
    completion_rate: float
    accuracy_rate: float
    dispute_rate: float
    total_transactions: int
    last_updated: datetime

    model_config = {"from_attributes": True}


class ReputationEventResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    counterparty_agent_id: uuid.UUID | None
    event_type: ReputationEventType
    score_delta: float
    event_metadata: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReputationEventCreate(BaseModel):
    event_type: ReputationEventType
    counterparty_agent_id: uuid.UUID | None = Field(default=None)
    event_metadata: dict | None = Field(default=None)


class ReputationDetail(BaseModel):
    score: ReputationScoreResponse
    recent_events: list[ReputationEventResponse]
