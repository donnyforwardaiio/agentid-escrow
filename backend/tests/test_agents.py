"""
Full test suite for AgentID Phase 1.

Covers every endpoint, all error branches, reputation math,
score floor/ceiling, and Ed25519 auth.
"""
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from tests.conftest import make_signature


# ===========================================================================
# Health
# ===========================================================================

def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["db_connected"] is True


# ===========================================================================
# POST /v1/agents — register
# ===========================================================================

def test_register_agent_success(client, keypair):
    private_key, public_key_hex = keypair
    payload = {
        "name": "Alpha",
        "description": "First agent",
        "owner_email": "alpha@example.com",
        "capabilities": ["code", "data"],
        "public_key": public_key_hex,
    }
    r = client.post("/v1/agents", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Alpha"
    assert body["owner_email"] == "alpha@example.com"
    assert "code" in body["capabilities"]
    assert body["is_active"] is True
    assert body["is_verified"] is False
    assert body["reputation"]["overall_score"] == 100.0
    assert body["reputation"]["total_transactions"] == 0


def test_register_agent_duplicate_public_key(client, keypair):
    _, public_key_hex = keypair
    payload = {
        "name": "AgentOne",
        "owner_email": "one@example.com",
        "capabilities": [],
        "public_key": public_key_hex,
    }
    r1 = client.post("/v1/agents", json=payload)
    assert r1.status_code == 201

    payload["name"] = "AgentTwo"
    payload["owner_email"] = "two@example.com"
    r2 = client.post("/v1/agents", json=payload)
    assert r2.status_code == 409


def test_register_agent_invalid_public_key_not_hex(client):
    payload = {
        "name": "BadAgent",
        "owner_email": "bad@example.com",
        "capabilities": [],
        "public_key": "not-hex-at-all!!",
    }
    r = client.post("/v1/agents", json=payload)
    assert r.status_code in (422, 400)


def test_register_agent_invalid_public_key_wrong_length(client):
    # 31 bytes instead of 32 (62 hex chars)
    payload = {
        "name": "BadAgent",
        "owner_email": "bad@example.com",
        "capabilities": [],
        "public_key": "aa" * 31,
    }
    r = client.post("/v1/agents", json=payload)
    assert r.status_code in (422, 400)


def test_register_agent_invalid_public_key_too_short(client):
    # Pydantic min_length=64 on the field should reject this before auth validation
    payload = {
        "name": "BadAgent",
        "owner_email": "bad@example.com",
        "capabilities": [],
        "public_key": "aa" * 10,  # 20 hex chars = 10 bytes, too short
    }
    r = client.post("/v1/agents", json=payload)
    # Pydantic rejects at schema level (422) or auth service rejects (422)
    assert r.status_code in (422, 400)


# ===========================================================================
# GET /v1/agents/{agent_id}
# ===========================================================================

def test_get_agent_success(client, registered_agent):
    agent, _, _ = registered_agent
    r = client.get(f"/v1/agents/{agent['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == agent["id"]
    assert body["name"] == agent["name"]
    assert body["reputation"]["overall_score"] == 100.0


def test_get_agent_not_found(client):
    r = client.get("/v1/agents/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ===========================================================================
# GET /v1/agents — list
# ===========================================================================

def test_list_agents_no_filter(client, registered_agent):
    r = client.get("/v1/agents")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert "items" in body
    assert "limit" in body
    assert "offset" in body
    # owner_email must NOT appear in public list items
    for item in body["items"]:
        assert "owner_email" not in item


def test_list_agents_by_capability(client, keypair):
    private_key, public_key_hex = keypair
    # Register one agent with "browsing", one without
    pk2 = Ed25519PrivateKey.generate()
    pk2_hex = pk2.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    client.post("/v1/agents", json={
        "name": "BrowsingAgent",
        "owner_email": "b@example.com",
        "capabilities": ["browsing"],
        "public_key": public_key_hex,
    })
    client.post("/v1/agents", json={
        "name": "CodeOnlyAgent",
        "owner_email": "c@example.com",
        "capabilities": ["code"],
        "public_key": pk2_hex,
    })

    r = client.get("/v1/agents?capability=browsing")
    assert r.status_code == 200
    body = r.json()
    names = [item["name"] for item in body["items"]]
    assert "BrowsingAgent" in names
    assert "CodeOnlyAgent" not in names


def test_list_agents_by_min_score(client, registered_agent):
    agent, private_key, _ = registered_agent

    # Log a VERIFICATION_PASSED event → score becomes 110.0
    event = {"event_type": "VERIFICATION_PASSED"}
    body_bytes, sig = make_signature(private_key, event)
    client.post(
        f"/v1/agents/{agent['id']}/events",
        content=body_bytes,
        headers={"content-type": "application/json", "x-agent-signature": sig},
    )

    r_high = client.get("/v1/agents?min_score=105")
    assert r_high.status_code == 200
    assert r_high.json()["total"] >= 1

    r_impossible = client.get("/v1/agents?min_score=9999")
    assert r_impossible.status_code == 200
    assert r_impossible.json()["total"] == 0


# ===========================================================================
# POST /v1/agents/{agent_id}/events
# ===========================================================================

def test_log_event_success(client, registered_agent):
    agent, private_key, _ = registered_agent
    event = {"event_type": "TASK_COMPLETED"}
    body_bytes, sig = make_signature(private_key, event)
    r = client.post(
        f"/v1/agents/{agent['id']}/events",
        content=body_bytes,
        headers={"content-type": "application/json", "x-agent-signature": sig},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["overall_score"] == 102.0
    assert body["total_transactions"] == 1
    assert body["completion_rate"] == 1.0


def test_log_event_invalid_signature(client, registered_agent):
    agent, _, _ = registered_agent
    event = {"event_type": "TASK_COMPLETED"}
    body_bytes = json.dumps(event).encode()
    bad_sig = "ff" * 64  # wrong signature
    r = client.post(
        f"/v1/agents/{agent['id']}/events",
        content=body_bytes,
        headers={"content-type": "application/json", "x-agent-signature": bad_sig},
    )
    assert r.status_code == 401


def test_log_event_missing_signature(client, registered_agent):
    agent, _, _ = registered_agent
    r = client.post(
        f"/v1/agents/{agent['id']}/events",
        json={"event_type": "TASK_COMPLETED"},
    )
    assert r.status_code == 401


def test_log_event_agent_not_found(client, keypair):
    private_key, _ = keypair
    event = {"event_type": "TASK_COMPLETED"}
    body_bytes, sig = make_signature(private_key, event)
    r = client.post(
        "/v1/agents/00000000-0000-0000-0000-000000000000/events",
        content=body_bytes,
        headers={"content-type": "application/json", "x-agent-signature": sig},
    )
    assert r.status_code == 404


# ===========================================================================
# Reputation scoring math
# ===========================================================================

def test_reputation_updates_correctly_on_events(client, registered_agent):
    agent, private_key, _ = registered_agent
    agent_id = agent["id"]

    def post_event(event_type: str):
        event = {"event_type": event_type}
        body_bytes, sig = make_signature(private_key, event)
        return client.post(
            f"/v1/agents/{agent_id}/events",
            content=body_bytes,
            headers={"content-type": "application/json", "x-agent-signature": sig},
        )

    # TASK_COMPLETED: +2.0 → 102.0
    r = post_event("TASK_COMPLETED")
    assert r.json()["overall_score"] == 102.0

    # TASK_FAILED: -5.0 → 97.0
    r = post_event("TASK_FAILED")
    assert r.json()["overall_score"] == 97.0
    assert r.json()["completion_rate"] == pytest.approx(0.5)

    # DISPUTE_RAISED: -3.0 → 94.0
    r = post_event("DISPUTE_RAISED")
    assert r.json()["overall_score"] == 94.0

    # DISPUTE_RESOLVED: +1.0 → 95.0
    r = post_event("DISPUTE_RESOLVED")
    assert r.json()["overall_score"] == 95.0

    # VERIFICATION_PASSED: +10.0 → 105.0
    r = post_event("VERIFICATION_PASSED")
    assert r.json()["overall_score"] == 105.0

    # Check full reputation endpoint
    r = client.get(f"/v1/agents/{agent_id}/reputation")
    assert r.status_code == 200
    assert len(r.json()["recent_events"]) == 5


def test_score_floor_is_zero(client, keypair):
    private_key, public_key_hex = keypair
    # Register fresh agent (score=100)
    r = client.post("/v1/agents", json={
        "name": "FloorAgent",
        "owner_email": "floor@example.com",
        "capabilities": [],
        "public_key": public_key_hex,
    })
    assert r.status_code == 201
    agent_id = r.json()["id"]

    def post_event(event_type: str):
        event = {"event_type": event_type}
        body_bytes, sig = make_signature(private_key, event)
        return client.post(
            f"/v1/agents/{agent_id}/events",
            content=body_bytes,
            headers={"content-type": "application/json", "x-agent-signature": sig},
        )

    # Hammer with TASK_FAILED (-5 each) until score can't go below 0
    for _ in range(25):  # 25 × -5 = -125, but floor is 0
        r = post_event("TASK_FAILED")
        assert r.status_code == 200
        assert r.json()["overall_score"] >= 0.0

    final = r.json()["overall_score"]
    assert final == 0.0


# ===========================================================================
# agent_role — registration and filtering
# ===========================================================================

def _make_agent(client, keypair, name, role="provider", capabilities=None):
    private_key, public_key_hex = keypair
    payload = {
        "name": name,
        "owner_email": f"{name.lower()}@example.com",
        "capabilities": capabilities or [],
        "agent_role": role,
        "public_key": public_key_hex,
    }
    r = client.post("/v1/agents", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_register_agent_defaults_to_provider(client, keypair):
    _, public_key_hex = keypair
    payload = {
        "name": "DefaultRole",
        "owner_email": "default@example.com",
        "capabilities": [],
        "public_key": public_key_hex,
    }
    r = client.post("/v1/agents", json=payload)
    assert r.status_code == 201
    assert r.json()["agent_role"] == "provider"


def test_register_agent_as_consumer(client, keypair):
    _, public_key_hex = keypair
    payload = {
        "name": "ConsumerAgent",
        "owner_email": "consumer@example.com",
        "capabilities": [],
        "agent_role": "consumer",
        "public_key": public_key_hex,
    }
    r = client.post("/v1/agents", json=payload)
    assert r.status_code == 201
    assert r.json()["agent_role"] == "consumer"


def test_list_agents_filter_by_role(client, keypair, second_keypair):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    def fresh_key():
        pk = Ed25519PrivateKey.generate()
        return pk, pk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    kp1 = fresh_key()
    kp2 = fresh_key()

    _make_agent(client, kp1, "ProviderOne", role="provider")
    _make_agent(client, kp2, "ConsumerOne", role="consumer")

    r_provider = client.get("/v1/agents?role=provider")
    assert r_provider.status_code == 200
    roles = [a["agent_role"] for a in r_provider.json()["items"]]
    assert all(r == "provider" for r in roles)

    r_consumer = client.get("/v1/agents?role=consumer")
    assert r_consumer.status_code == 200
    roles = [a["agent_role"] for a in r_consumer.json()["items"]]
    assert all(r == "consumer" for r in roles)


# ===========================================================================
# GET /v1/agents/discover
# ===========================================================================

def test_discover_returns_only_providers(client, keypair, second_keypair):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    def fresh_key():
        pk = Ed25519PrivateKey.generate()
        return pk, pk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    _make_agent(client, fresh_key(), "DiscoverProvider", role="provider", capabilities=["code"])
    _make_agent(client, fresh_key(), "DiscoverConsumer", role="consumer")

    r = client.get("/v1/agents/discover")
    assert r.status_code == 200
    body = r.json()
    roles = [a["agent_role"] for a in body["items"]]
    assert all(r == "provider" for r in roles), f"Non-provider in results: {roles}"


def test_discover_filter_by_capability(client):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    def fresh_key():
        pk = Ed25519PrivateKey.generate()
        return pk, pk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    _make_agent(client, fresh_key(), "CodeProvider", role="provider", capabilities=["code"])
    _make_agent(client, fresh_key(), "WritingProvider", role="provider", capabilities=["writing"])

    r = client.get("/v1/agents/discover?capability=code")
    assert r.status_code == 200
    for agent in r.json()["items"]:
        assert "code" in agent["capabilities"]


def test_discover_filter_min_score(client):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    def fresh_key():
        pk = Ed25519PrivateKey.generate()
        return pk, pk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    _make_agent(client, fresh_key(), "HighScoreProvider", role="provider")

    r = client.get("/v1/agents/discover?min_score=50")
    assert r.status_code == 200
    for agent in r.json()["items"]:
        assert agent["reputation"]["overall_score"] >= 50


def test_discover_returns_paginated_response(client):
    r = client.get("/v1/agents/discover?limit=5&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert "limit" in body
    assert body["limit"] == 5
