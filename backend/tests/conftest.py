"""
Test configuration and shared fixtures.

Uses SQLite (in-memory per session) so tests run without a live Postgres DB.
Each test gets its own DB transaction that is rolled back on teardown,
giving full isolation with no test-order dependencies.
"""
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# One shared in-memory SQLite engine for the whole test session
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite:///./test_agentid.db"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once at the start; drop them at the end."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Per-test fixtures: isolated DB session + TestClient
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session(create_tables):
    """
    Yield a session scoped to a single transaction.
    Everything is rolled back after the test — no data leaks between tests.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with get_db overridden to use the test session."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Ed25519 keypair helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def keypair():
    """Return (private_key, public_key_hex) for a freshly generated Ed25519 key."""
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = (
        private_key.public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
        .hex()
    )
    return private_key, public_key_hex


def make_signature(private_key: Ed25519PrivateKey, body: dict) -> tuple[bytes, str]:
    """Serialize body to JSON bytes and return (body_bytes, hex_signature)."""
    body_bytes = json.dumps(body).encode()
    sig_hex = private_key.sign(body_bytes).hex()
    return body_bytes, sig_hex


# ---------------------------------------------------------------------------
# Registered-agent fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def registered_agent(client, keypair):
    """Register a valid agent and return (response_json, private_key, public_key_hex)."""
    private_key, public_key_hex = keypair
    payload = {
        "name": "FixtureAgent",
        "description": "Agent created by test fixture",
        "owner_email": "fixture@example.com",
        "capabilities": ["code", "research"],
        "public_key": public_key_hex,
    }
    r = client.post("/v1/agents", json=payload)
    assert r.status_code == 201, f"Fixture registration failed: {r.text}"
    return r.json(), private_key, public_key_hex
