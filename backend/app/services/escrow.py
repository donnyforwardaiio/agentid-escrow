"""
Escrow service — handles fee calculation, status transitions,
Stripe PaymentIntent creation, and reputation updates on completion.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.escrow import Dispute, DisputeStatus, EscrowStatus, EscrowTransaction
from app.models.audit import AuditLog
from app.services.reputation import update_reputation
from app.models.reputation import ReputationEventType

settings = get_settings()

# Fee rate: 1.5% on escrow transactions
FEE_RATE = Decimal("0.015")
# Cumulative threshold above which fees apply (per payer)
FEE_THRESHOLD = Decimal("10000.00")
# Auto-release window after funding (hours)
DISPUTE_WINDOW_HOURS = 24


def _configure_stripe() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def calculate_fee(amount: Decimal, payer_cumulative: Decimal) -> Decimal:
    """
    Fee is 1.5% of the transaction amount, but only on the portion
    of cumulative volume that exceeds $10,000.
    """
    if payer_cumulative + amount <= FEE_THRESHOLD:
        return Decimal("0.00")
    # Amount that falls above the threshold
    taxable = (payer_cumulative + amount) - max(payer_cumulative, FEE_THRESHOLD)
    return (taxable * FEE_RATE).quantize(Decimal("0.01"))


def get_payer_cumulative(db: Session, payer_agent_id: UUID) -> Decimal:
    """Sum of all completed/funded escrow amounts for this payer."""
    from sqlalchemy import func
    result = (
        db.query(func.coalesce(func.sum(EscrowTransaction.amount), 0))
        .filter(
            EscrowTransaction.payer_agent_id == payer_agent_id,
            EscrowTransaction.status.in_([EscrowStatus.FUNDED, EscrowStatus.COMPLETED]),
        )
        .scalar()
    )
    return Decimal(str(result))


def create_escrow(
    db: Session,
    payer_agent_id: UUID,
    payee_agent_id: UUID,
    amount: Decimal,
    currency: str,
    task_description: str,
) -> EscrowTransaction:
    """Create a new escrow transaction in PENDING state."""
    cumulative = get_payer_cumulative(db, payer_agent_id)
    fee = calculate_fee(amount, cumulative)

    tx = EscrowTransaction(
        payer_agent_id=payer_agent_id,
        payee_agent_id=payee_agent_id,
        amount=amount,
        fee_amount=fee,
        currency=currency,
        task_description=task_description,
        status=EscrowStatus.PENDING,
    )
    db.add(tx)
    db.flush()  # get the id before commit

    db.add(AuditLog(
        action="escrow.created",
        resource_type="escrow_transaction",
        resource_id=tx.id,
        request_data={"amount": str(amount), "fee": str(fee), "currency": currency},
    ))
    db.commit()
    db.refresh(tx)
    return tx


def fund_escrow(db: Session, tx: EscrowTransaction) -> EscrowTransaction:
    """
    Create a Stripe PaymentIntent and mark the escrow as FUNDED.
    Sets auto-release time to 24h from now.
    """
    _configure_stripe()

    total_cents = int((tx.amount + tx.fee_amount) * 100)
    intent = stripe.PaymentIntent.create(
        amount=total_cents,
        currency=tx.currency.lower(),
        metadata={
            "escrow_id": str(tx.id),
            "payer_agent_id": str(tx.payer_agent_id),
            "payee_agent_id": str(tx.payee_agent_id),
        },
        capture_method="automatic",
    )

    tx.stripe_payment_intent_id = intent["id"]
    tx.status = EscrowStatus.FUNDED
    tx.release_at = datetime.now(timezone.utc) + timedelta(hours=DISPUTE_WINDOW_HOURS)
    tx.updated_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        action="escrow.funded",
        resource_type="escrow_transaction",
        resource_id=tx.id,
        request_data={"stripe_payment_intent_id": intent["id"]},
    ))
    db.commit()
    db.refresh(tx)
    return tx


def release_escrow(db: Session, tx: EscrowTransaction) -> EscrowTransaction:
    """Release funds to payee and update reputation for both agents."""
    if tx.status != EscrowStatus.FUNDED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot release escrow in status '{tx.status.value}'",
        )

    tx.status = EscrowStatus.COMPLETED
    tx.updated_at = datetime.now(timezone.utc)

    # Update reputation: payee completed task, payer is counterparty
    update_reputation(
        agent_id=tx.payee_agent_id,
        event_type=ReputationEventType.TASK_COMPLETED,
        counterparty_agent_id=tx.payer_agent_id,
        event_metadata={"escrow_id": str(tx.id)},
        db=db,
    )
    update_reputation(
        agent_id=tx.payer_agent_id,
        event_type=ReputationEventType.TASK_COMPLETED,
        counterparty_agent_id=tx.payee_agent_id,
        event_metadata={"escrow_id": str(tx.id)},
        db=db,
    )

    db.add(AuditLog(
        action="escrow.released",
        resource_type="escrow_transaction",
        resource_id=tx.id,
        request_data={},
    ))
    db.commit()
    db.refresh(tx)
    return tx


def open_dispute(
    db: Session,
    tx: EscrowTransaction,
    opened_by_agent_id: UUID,
    reason: str,
) -> Dispute:
    """Open a dispute on a FUNDED escrow."""
    if tx.status != EscrowStatus.FUNDED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot dispute escrow in status '{tx.status.value}'",
        )
    if tx.dispute:
        raise HTTPException(status_code=409, detail="A dispute already exists for this escrow")

    tx.status = EscrowStatus.DISPUTED
    tx.updated_at = datetime.now(timezone.utc)

    dispute = Dispute(
        transaction_id=tx.id,
        opened_by_agent_id=opened_by_agent_id,
        reason=reason,
        status=DisputeStatus.OPEN,
    )
    db.add(dispute)

    db.add(AuditLog(
        action="dispute.opened",
        resource_type="dispute",
        resource_id=tx.id,
        request_data={"opened_by": str(opened_by_agent_id)},
    ))
    db.commit()
    db.refresh(dispute)
    return dispute


def handle_stripe_webhook(db: Session, payload: bytes, sig_header: str) -> dict:
    """Verify Stripe signature and process payment events."""
    _configure_stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event_type = event["type"]
    intent_id = event["data"]["object"].get("id")

    if event_type == "payment_intent.succeeded" and intent_id:
        tx = (
            db.query(EscrowTransaction)
            .filter(EscrowTransaction.stripe_payment_intent_id == intent_id)
            .first()
        )
        if tx and tx.status == EscrowStatus.PENDING:
            tx.status = EscrowStatus.FUNDED
            tx.release_at = datetime.now(timezone.utc) + timedelta(hours=DISPUTE_WINDOW_HOURS)
            tx.updated_at = datetime.now(timezone.utc)
            db.add(AuditLog(
                action="escrow.funded_via_webhook",
                resource_type="escrow_transaction",
                resource_id=tx.id,
                request_data={"stripe_event_id": event["id"]},
            ))
            db.commit()

    elif event_type == "payment_intent.payment_failed" and intent_id:
        tx = (
            db.query(EscrowTransaction)
            .filter(EscrowTransaction.stripe_payment_intent_id == intent_id)
            .first()
        )
        if tx:
            tx.status = EscrowStatus.CANCELLED
            tx.updated_at = datetime.now(timezone.utc)
            db.commit()

    return {"status": "processed", "event_type": event_type}
