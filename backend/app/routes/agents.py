import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Agent, AuditLog, ReputationEvent, ReputationScore
from app.models.reputation import ReputationEventType
from app.schemas.agents import AgentCreate, AgentPublic, AgentResponse, AgentRoleEnum
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
# GHL helper — fire-and-forget contact creation
# ---------------------------------------------------------------------------

def _create_ghl_contact(email: str, name: str, agent_id: str) -> None:
    """
    Create a contact in GoHighLevel tagged 'agent-registered'.
    Called as a background task — errors are logged but never surface to the caller.
    """
    if not settings.GHL_LOCATION_ACCESS_TOKEN:
        print("[WARN] GHL_LOCATION_ACCESS_TOKEN not set — skipping GHL contact creation for agent registration")
        return

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{settings.GHL_API_URL}/contacts/",
                headers={
                    "Authorization": f"Bearer {settings.GHL_LOCATION_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "Version": "2021-07-28",
                },
                json={
                    "locationId": settings.GHL_LOCATION_ID,
                    "email": email,
                    "firstName": name,
                    "source": "agent_registration",
                    "tags": ["agent-registered"],
                    "customFields": [
                        {"key": "agent_id", "field_value": agent_id},
                    ],
                },
            )
            print(f"[INFO] GHL agent-registration contact: {response.status_code} — {response.text[:300]}")
    except Exception as exc:
        print(f"[ERROR] GHL contact creation failed for agent {agent_id}: {exc}")


# ---------------------------------------------------------------------------
# POST /v1/agents  — register a new agent
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agent",
)
def register_agent(body: AgentCreate, request: Request, db: DbDep, background_tasks: BackgroundTasks):
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
        agent_role=body.agent_role.value,
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

    # Fire GHL contact creation in the background — tagged 'agent-registered'
    background_tasks.add_task(
        _create_ghl_contact,
        email=agent.owner_email,
        name=agent.name,
        agent_id=str(agent.id),
    )

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
    role: AgentRoleEnum | None = Query(default=None, description="Filter by agent role: 'consumer' or 'provider'"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    from sqlalchemy import cast, String
    query = db.query(Agent).filter(Agent.is_active.is_(True))

    if capability:
        query = query.filter(
            cast(Agent.capabilities, String).contains(f'"{capability}"')
        )

    if role is not None:
        query = query.filter(Agent.agent_role == role.value)

    if min_score is not None:
        query = (
            query
            .join(ReputationScore, ReputationScore.agent_id == Agent.id)
            .filter(ReputationScore.overall_score >= min_score)
        )

    total = query.count()

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
# GET /v1/agents/discover  — discovery endpoint for consumer agents
# NOTE: must be registered BEFORE /{agent_id} to avoid being swallowed by
# the UUID path parameter route.
# ---------------------------------------------------------------------------

@router.get(
    "/discover",
    response_model=PaginatedResponse[AgentPublic],
    summary="Discover provider agents — optimised for consumer agents finding services",
)
def discover_agents(
    db: DbDep,
    capability: str | None = Query(default=None, description="Required capability (e.g. 'code', 'research')"),
    min_score: float | None = Query(default=None, description="Minimum reputation score (0–100)"),
    min_transactions: int | None = Query(default=None, description="Minimum completed transactions"),
    verified_only: bool = Query(default=False, description="Only return verified agents"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Purpose-built discovery endpoint for consumer agents seeking providers.
    Always filters to active provider agents, ordered by reputation score descending.
    Use this endpoint to find and evaluate agents before hiring them.
    """
    from sqlalchemy import cast, String
    query = (
        db.query(Agent)
        .filter(Agent.is_active.is_(True))
        .filter(Agent.agent_role == "provider")
    )

    if capability:
        query = query.filter(
            cast(Agent.capabilities, String).contains(f'"{capability}"')
        )

    if verified_only:
        query = query.filter(Agent.is_verified.is_(True))

    # Always join reputation for ordering; filter on it if thresholds given
    query = query.join(ReputationScore, ReputationScore.agent_id == Agent.id)

    if min_score is not None:
        query = query.filter(ReputationScore.overall_score >= min_score)

    if min_transactions is not None:
        query = query.filter(ReputationScore.total_transactions >= min_transactions)

    total = query.count()

    agents = (
        query
        .order_by(ReputationScore.overall_score.desc())
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
