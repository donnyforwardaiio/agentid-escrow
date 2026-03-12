import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.reputation import ReputationEvent, ReputationEventType, ReputationScore

SCORE_FLOOR = 0.0
SCORE_CEILING = 1000.0

# Score deltas per event type
SCORE_DELTAS: dict[ReputationEventType, float] = {
    ReputationEventType.TASK_COMPLETED: +2.0,
    ReputationEventType.TASK_FAILED: -5.0,
    ReputationEventType.DISPUTE_RAISED: -3.0,
    ReputationEventType.DISPUTE_RESOLVED: +1.0,
    ReputationEventType.VERIFICATION_PASSED: +10.0,
}


def update_reputation(
    agent_id: uuid.UUID,
    event_type: ReputationEventType,
    counterparty_agent_id: uuid.UUID | None,
    event_metadata: dict | None,
    db: Session,
) -> tuple[ReputationScore, ReputationEvent]:
    """
    Log a reputation event and update the agent's reputation score atomically.
    Returns the updated ReputationScore and the new ReputationEvent.
    """
    delta = SCORE_DELTAS[event_type]

    # Fetch current score (must already exist)
    score = db.query(ReputationScore).filter(ReputationScore.agent_id == agent_id).first()
    if not score:
        raise ValueError(f"No ReputationScore found for agent {agent_id}")

    # Create the event record
    event = ReputationEvent(
        agent_id=agent_id,
        counterparty_agent_id=counterparty_agent_id,
        event_type=event_type.value,
        score_delta=delta,
        event_metadata=event_metadata,
    )
    db.add(event)

    # Apply delta with floor/ceiling
    new_score = max(SCORE_FLOOR, min(SCORE_CEILING, score.overall_score + delta))
    score.overall_score = new_score
    score.last_updated = datetime.now(timezone.utc)

    # Update counters and rates
    if event_type in (ReputationEventType.TASK_COMPLETED, ReputationEventType.TASK_FAILED):
        score.total_transactions += 1
        _recalculate_rates(agent_id, score, db, pending_event_type=event_type)
    elif event_type == ReputationEventType.DISPUTE_RAISED:
        score.total_transactions += 1
        _recalculate_rates(agent_id, score, db, pending_event_type=event_type)

    db.flush()
    return score, event


def _recalculate_rates(
    agent_id: uuid.UUID,
    score: ReputationScore,
    db: Session,
    pending_event_type: ReputationEventType,
) -> None:
    """
    Recalculate completion_rate and dispute_rate from the full event history.
    Called after flushing the new event so counts include the latest record.
    """
    from sqlalchemy import func as sqlfunc

    counts: dict[str, int] = {}
    rows = (
        db.query(ReputationEvent.event_type, sqlfunc.count(ReputationEvent.id))
        .filter(ReputationEvent.agent_id == agent_id)
        .group_by(ReputationEvent.event_type)
        .all()
    )
    for event_type_val, count in rows:
        counts[event_type_val] = count

    # Add the pending event (not yet flushed to DB count)
    counts[pending_event_type.value] = counts.get(pending_event_type.value, 0) + 1

    completed = counts.get(ReputationEventType.TASK_COMPLETED.value, 0)
    failed = counts.get(ReputationEventType.TASK_FAILED.value, 0)
    disputed = counts.get(ReputationEventType.DISPUTE_RAISED.value, 0)
    task_total = completed + failed

    score.completion_rate = (completed / task_total) if task_total > 0 else 1.0
    score.dispute_rate = (disputed / score.total_transactions) if score.total_transactions > 0 else 0.0


def calculate_rates(agent_id: uuid.UUID, db: Session) -> dict:
    """Return current rate stats for an agent."""
    score = db.query(ReputationScore).filter(ReputationScore.agent_id == agent_id).first()
    if not score:
        return {}
    return {
        "completion_rate": score.completion_rate,
        "accuracy_rate": score.accuracy_rate,
        "dispute_rate": score.dispute_rate,
        "total_transactions": score.total_transactions,
    }
