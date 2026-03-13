"""
Escrow API routes — /v1/escrow
"""
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.escrow import EscrowTransaction
from app.schemas.escrow import (
    DisputeCreate,
    DisputeResponse,
    EscrowCreate,
    EscrowResponse,
)
from app.services import escrow as escrow_svc

router = APIRouter(prefix="/v1/escrow", tags=["escrow"])


def _get_tx_or_404(db: Session, escrow_id: UUID) -> EscrowTransaction:
    tx = db.query(EscrowTransaction).filter(EscrowTransaction.id == escrow_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Escrow transaction not found")
    return tx


# ── POST /v1/escrow ───────────────────────────────────────────────────────────
@router.post("", response_model=EscrowResponse, status_code=201)
def create_escrow(payload: EscrowCreate, db: Session = Depends(get_db)):
    """Create a new escrow transaction (status: pending)."""
    # Verify both agents exist
    from app.models.agent import Agent
    for agent_id in [payload.payer_agent_id, payload.payee_agent_id]:
        if not db.query(Agent).filter(Agent.id == agent_id).first():
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return escrow_svc.create_escrow(
        db=db,
        payer_agent_id=payload.payer_agent_id,
        payee_agent_id=payload.payee_agent_id,
        amount=payload.amount,
        currency=payload.currency,
        task_description=payload.task_description,
    )


# ── GET /v1/escrow/{id} ───────────────────────────────────────────────────────
@router.get("/{escrow_id}", response_model=EscrowResponse)
def get_escrow(escrow_id: UUID, db: Session = Depends(get_db)):
    """Get escrow transaction details."""
    return _get_tx_or_404(db, escrow_id)


# ── POST /v1/escrow/{id}/fund ─────────────────────────────────────────────────
@router.post("/{escrow_id}/fund", response_model=EscrowResponse)
def fund_escrow(escrow_id: UUID, db: Session = Depends(get_db)):
    """
    Create a Stripe PaymentIntent and mark escrow as funded.
    Starts the 24h dispute window.
    """
    tx = _get_tx_or_404(db, escrow_id)
    if tx.status.value != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Escrow is already in status '{tx.status.value}'",
        )
    try:
        return escrow_svc.fund_escrow(db=db, tx=tx)
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=402, detail=str(e))


# ── POST /v1/escrow/{id}/release ──────────────────────────────────────────────
@router.post("/{escrow_id}/release", response_model=EscrowResponse)
def release_escrow(escrow_id: UUID, db: Session = Depends(get_db)):
    """Release funds to payee. Marks escrow as completed."""
    tx = _get_tx_or_404(db, escrow_id)
    return escrow_svc.release_escrow(db=db, tx=tx)


# ── POST /v1/escrow/{id}/dispute ──────────────────────────────────────────────
@router.post("/{escrow_id}/dispute", response_model=DisputeResponse, status_code=201)
def open_dispute(
    escrow_id: UUID,
    payload: DisputeCreate,
    db: Session = Depends(get_db),
):
    """Open a dispute on a funded escrow."""
    tx = _get_tx_or_404(db, escrow_id)
    return escrow_svc.open_dispute(
        db=db,
        tx=tx,
        opened_by_agent_id=payload.opened_by_agent_id,
        reason=payload.reason,
    )


# ── POST /v1/webhooks/stripe ──────────────────────────────────────────────────
stripe_router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@stripe_router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    return escrow_svc.handle_stripe_webhook(db=db, payload=payload, sig_header=sig_header)
