from decimal import Decimal
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.escrow import DisputeStatus, EscrowStatus


# ── Escrow Transaction ────────────────────────────────────────────────────────

class EscrowCreate(BaseModel):
    payer_agent_id: UUID
    payee_agent_id: UUID
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    task_description: str = Field(..., min_length=10, max_length=2000)

    @model_validator(mode="after")
    def payer_ne_payee(self) -> "EscrowCreate":
        if self.payer_agent_id == self.payee_agent_id:
            raise ValueError("payer_agent_id and payee_agent_id must be different")
        return self


class EscrowResponse(BaseModel):
    id: UUID
    payer_agent_id: UUID
    payee_agent_id: UUID
    amount: Decimal
    fee_amount: Decimal
    currency: str
    status: EscrowStatus
    task_description: str
    stripe_payment_intent_id: Optional[str] = None
    release_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Dispute ───────────────────────────────────────────────────────────────────

class DisputeCreate(BaseModel):
    opened_by_agent_id: UUID
    reason: str = Field(..., min_length=10, max_length=2000)


class DisputeResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    opened_by_agent_id: UUID
    reason: str
    status: DisputeStatus
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Stripe Webhook ────────────────────────────────────────────────────────────

class StripeWebhookEvent(BaseModel):
    id: str
    type: str
    data: dict
