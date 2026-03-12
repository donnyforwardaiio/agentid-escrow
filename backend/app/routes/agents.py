import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Agent, AuditLog, ReputationEvent, ReputationScore
from app.models.reputation import ReputationEventType
from app.schemas.agents import AgentCreate, AgentPublic, AgentResponse
from app.schemas.common import PaginatedResponse
from app.schemas.reputation import (
    ReputationDetail,
    ReputationEventCreate,
    ReputationEventResponse,
    ReputationScoreResponse,
)
from app.services.auth import get_agent_or_404, validate_public_key, verify_agent_signature
from app.services.reputation import update_reputation

router = APIRouter(prefix="/v1/agents", tags=["agents"])

DbDep = Annotated[Session, Depends(get_db)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_reputation(agent_id: uuid.UUID, db: Session) -> ReputationScoreResponse | None:
    score = db.query(ReputationScore).filter(ReputationScore.agent_id == agent_id).first()
    if score:
        return ReputationScoreResponse.model_validate(score)
    return None


def _write_audit(
    db: Session,
    action: str,
    agent_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    request_data: dict | None = None,
    ip_address: str | None = None,
) -> None:
    log = AuditLog(
        agent_id=agent_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_data=request_data,
        ip_address=ip_address,
    )
    db.add(log)


# ---------------------------------------------------------------------------
# POST /v1/agents  — register a new agent
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agent",
)
def register_agent(body: AgentCreate, request: Request, db: DbDep):
    # Validate Ed25519 public key
    validate_public_key(body.public_key)

    # Check duplicate public key
    existing = db.query(Agent).filter(Agent.public_key == body.public_key).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agent with this public key already exists.",
        )

    # Create agent
    agent = Agent(
        public_key=body.public_key,
        name=body.name,
        description=body.description,
        owner_email=body.owner_email,
        capabilities=[c.value for c in body.capabilities],
    )
    db.add(agent)
    db.flush()  # get agent.id before committing

    # Create initial reputation score
    rep = ReputationScore(agent_id=agent.id)
    db.add(rep)

    # Audit log
    _write_audit(
        db,
        action="agent.register",
        agent_id=agent.id,
        resource_type="agent",
        resource_id=agent.id,
        request_data={"name": agent.name, "owner_email": agent.owner_email},
        ip_address=request.client.host if request.client else None,
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agent with this public key already exists.",
        )

    db.refresh(agent)
    return AgentResponse(
        **{c.name: getattr(agent, c.name) for c in agent.__table__.columns},
        reputation=_get_reputation(agent.id, db),
    )


# ---------------------------------------------------------------------------
# GET /v1/agents/{agent_id}  — fetch single agent
# ---------------------------------------------------------------------------

@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get a single agent by ID",
)
def get_agent(agent_id: uuid.UUID, db: DbDep):
    agent = get_agent_or_404(agent_id, db)
    return AgentResponse(
        **{c.name: getattr(agent, c.name) for c in agent.__table__.columns},
        reputation=_get_reputation(agent.id, db),
    )


# ---------------------------------------------------------------------------
# GET /v1/agents  — list agents with optional filters
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=PaginatedResponse[AgentPublic],
    summary="List agents with optional filters",
)
def list_agents(
    db: DbDep,
    capability: str | None = Query(default=None, description="Filter by capability"),
    min_score: float | None = Query(default=None, description="Minimum overall score"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = (
        db.query(Agent)
        .filter(Agent.is_active.is_(True))
    )

    if capability:
        # Cross-dialect: cast JSON column to text and search for the quoted value.
        # On PostgreSQL this hits the JSONB text representation; on SQLite the JSON
        # is stored as text already. Both produce correct results for string arrays.
        from sqlalchemy import cast, String
        query = query.filter(
            cast(Agent.capabilities, String).contains(f'"{capability}"')
        )

    if min_score is not None:
        query = (
            query
            .join(ReputationScore, ReputationScore.agent_id == Agent.id)
            .filter(ReputationScore.overall_score >= min_score)
        )

    total = query.count()

    # Order by reputation score descending (join if not already joined)
    if min_score is None:
        query = query.outerjoin(ReputationScore, ReputationScore.agent_id == Agent.id)

    agents = (
        query
        .order_by(ReputationScore.overall_score.desc().nulls_last())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        AgentPublic(
            **{c.name: getattr(a, c.name) for c in a.__table__.columns},
            reputation=_get_reputation(a.id, db),
        )
        for a in agents
    ]

    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# POST /v1/agents/{agent_id}/events  — log a reputation event (auth required)
# ---------------------------------------------------------------------------

@router.post(
    "/{agent_id}/events",
    response_model=ReputationScoreResponse,
    summary="Log a reputation event (requires Ed25519 signature)",
)
async def log_reputation_event(
    agent_id: uuid.UUID,
    body: ReputationEventCreate,
    request: Request,
    db: DbDep,
    x_agent_signature: Annotated[str | None, Header()] = None,
):
    if not x_agent_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Agent-Signature header is required.",
        )

    agent = get_agent_or_404(agent_id, db)

    # Verify signature over the raw request body
    raw_body = await request.body()
    verify_agent_signature(agent, x_agent_signature, raw_body)

    # Apply reputation update
    updated_score, event = update_reputation(
        agent_id=agent.id,
        event_type=body.event_type,
        counterparty_agent_id=body.counterparty_agent_id,
        event_metadata=body.event_metadata,
        db=db,
    )

    # Audit log
    _write_audit(
        db,
        action=f"agent.event.{body.event_type.value.lower()}",
        agent_id=agent.id,
        resource_type="reputation_event",
        resource_id=event.id,
        request_data={"event_type": body.event_type.value, "delta": event.score_delta},
        ip_address=request.client.host if request.client else None,
    )

    db.commit()
    db.refresh(updated_score)

    return ReputationScoreResponse.model_validate(updated_score)


# ---------------------------------------------------------------------------
# GET /v1/agents/{agent_id}/reputation  — public reputation detail
# ---------------------------------------------------------------------------

@router.get(
    "/{agent_id}/reputation",
    response_model=ReputationDetail,
    summary="Get agent reputation score and recent events",
)
def get_reputation(agent_id: uuid.UUID, db: DbDep):
    agent = get_agent_or_404(agent_id, db)

    score = db.query(ReputationScore).filter(ReputationScore.agent_id == agent.id).first()
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reputation score not found for this agent.",
        )

    recent_events = (
        db.query(ReputationEvent)
        .filter(ReputationEvent.agent_id == agent.id)
        .order_by(ReputationEvent.created_at.desc())
        .limit(10)
        .all()
    )

    return ReputationDetail(
        score=ReputationScoreResponse.model_validate(score),
        recent_events=[ReputationEventResponse.model_validate(e) for e in recent_events],
    )
