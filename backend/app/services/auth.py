import binascii
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Agent


def verify_agent_signature(agent: Agent, signature_hex: str, body: bytes) -> bool:
    """
    Verify that `signature_hex` is a valid Ed25519 signature over `body`
    using the agent's registered public key.

    Returns True on success, raises HTTPException(401) on failure.
    """
    try:
        public_key_bytes = bytes.fromhex(agent.public_key)
        signature_bytes = bytes.fromhex(signature_hex)
    except (ValueError, binascii.Error):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature or public key is not valid hex.",
        )

    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature_bytes, body)
        return True
    except InvalidSignature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature verification failed.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not verify signature: {exc}",
        )


def get_agent_or_404(agent_id: uuid.UUID, db: Session) -> Agent:
    """Fetch an active agent by ID or raise 404."""
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.is_active.is_(True)).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found.",
        )
    return agent


def validate_public_key(public_key_hex: str) -> None:
    """Validate that a hex string is a valid Ed25519 public key (32 bytes)."""
    try:
        key_bytes = bytes.fromhex(public_key_hex)
    except (ValueError, binascii.Error):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="public_key must be a hex-encoded string.",
        )
    if len(key_bytes) != 32:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"public_key must be 32 bytes (64 hex chars); got {len(key_bytes)} bytes.",
        )
    try:
        Ed25519PublicKey.from_public_bytes(key_bytes)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="public_key is not a valid Ed25519 public key.",
        )
