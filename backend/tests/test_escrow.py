"""
Tests for AgentEscrow API — Phase 2
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.models.escrow import EscrowStatus


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_agent(client: TestClient, keypair) -> dict:
    """Register a new agent and return the response JSON."""
    from tests.conftest import sign_body
    body = {
        "name": f"Agent-{uuid4().hex[:6]}",
        "public_key": keypair["public_key"],
        "owner_email": f"{uuid4().hex[:6]}@test.com",
        "capabilities": ["code"],
    }
    sig = sign_body(body, keypair["private_key_bytes"])
    resp = client.post(
        "/v1/agents",
        json=body,
        headers={"X-Agent-Signature": sig, "X-Agent-Public-Key": keypair["public_key"]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_escrow_payload(payer_id: str, payee_id: str, amount: str = "100.00") -> dict:
    return {
        "payer_agent_id": payer_id,
        "payee_agent_id": payee_id,
        "amount": amount,
        "currency": "USD",
        "task_description": "Analyse market data and return a JSON report",
    }


# ── POST /v1/escrow ───────────────────────────────────────────────────────────

def test_create_escrow_success(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    payload = make_escrow_payload(payer["id"], payee["id"])

    resp = client.post("/v1/escrow", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["payer_agent_id"] == payer["id"]
    assert data["payee_agent_id"] == payee["id"]
    assert Decimal(data["amount"]) == Decimal("100.00")


def test_create_escrow_same_payer_payee(client, ed25519_keypair):
    agent = create_agent(client, ed25519_keypair)
    payload = make_escrow_payload(agent["id"], agent["id"])

    resp = client.post("/v1/escrow", json=payload)
    assert resp.status_code == 422  # payer != payee validation


def test_create_escrow_unknown_payer(client, ed25519_keypair, second_keypair):
    payee = create_agent(client, second_keypair)
    payload = make_escrow_payload(str(uuid4()), payee["id"])

    resp = client.post("/v1/escrow", json=payload)
    assert resp.status_code == 404


def test_create_escrow_unknown_payee(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payload = make_escrow_payload(payer["id"], str(uuid4()))

    resp = client.post("/v1/escrow", json=payload)
    assert resp.status_code == 404


def test_create_escrow_negative_amount(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    payload = make_escrow_payload(payer["id"], payee["id"], amount="-50.00")

    resp = client.post("/v1/escrow", json=payload)
    assert resp.status_code == 422


def test_create_escrow_short_description(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    payload = {**make_escrow_payload(payer["id"], payee["id"]), "task_description": "short"}

    resp = client.post("/v1/escrow", json=payload)
    assert resp.status_code == 422


# ── GET /v1/escrow/{id} ───────────────────────────────────────────────────────

def test_get_escrow(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    created = client.post("/v1/escrow", json=make_escrow_payload(payer["id"], payee["id"])).json()

    resp = client.get(f"/v1/escrow/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_escrow_not_found(client):
    resp = client.get(f"/v1/escrow/{uuid4()}")
    assert resp.status_code == 404


# ── POST /v1/escrow/{id}/fund ─────────────────────────────────────────────────

def test_fund_escrow_success(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    tx = client.post("/v1/escrow", json=make_escrow_payload(payer["id"], payee["id"])).json()

    mock_intent = {"id": f"pi_{uuid4().hex}"}
    with patch("stripe.PaymentIntent.create", return_value=mock_intent):
        resp = client.post(f"/v1/escrow/{tx['id']}/fund")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "funded"
    assert data["stripe_payment_intent_id"] == mock_intent["id"]
    assert data["release_at"] is not None


def test_fund_escrow_already_funded(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    tx = client.post("/v1/escrow", json=make_escrow_payload(payer["id"], payee["id"])).json()

    mock_intent = {"id": f"pi_{uuid4().hex}"}
    with patch("stripe.PaymentIntent.create", return_value=mock_intent):
        client.post(f"/v1/escrow/{tx['id']}/fund")
        resp = client.post(f"/v1/escrow/{tx['id']}/fund")

    assert resp.status_code == 400


# ── POST /v1/escrow/{id}/release ─────────────────────────────────────────────

def test_release_escrow_success(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    tx = client.post("/v1/escrow", json=make_escrow_payload(payer["id"], payee["id"])).json()

    mock_intent = {"id": f"pi_{uuid4().hex}"}
    with patch("stripe.PaymentIntent.create", return_value=mock_intent):
        client.post(f"/v1/escrow/{tx['id']}/fund")

    resp = client.post(f"/v1/escrow/{tx['id']}/release")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_release_escrow_not_funded(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    tx = client.post("/v1/escrow", json=make_escrow_payload(payer["id"], payee["id"])).json()

    resp = client.post(f"/v1/escrow/{tx['id']}/release")
    assert resp.status_code == 400


# ── POST /v1/escrow/{id}/dispute ─────────────────────────────────────────────

def test_open_dispute_success(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    tx = client.post("/v1/escrow", json=make_escrow_payload(payer["id"], payee["id"])).json()

    mock_intent = {"id": f"pi_{uuid4().hex}"}
    with patch("stripe.PaymentIntent.create", return_value=mock_intent):
        client.post(f"/v1/escrow/{tx['id']}/fund")

    dispute_payload = {
        "opened_by_agent_id": payer["id"],
        "reason": "The task was not completed as described in the agreement",
    }
    resp = client.post(f"/v1/escrow/{tx['id']}/dispute", json=dispute_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert data["transaction_id"] == tx["id"]

    # Escrow status should now be disputed
    escrow = client.get(f"/v1/escrow/{tx['id']}").json()
    assert escrow["status"] == "disputed"


def test_open_dispute_on_pending_escrow(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    tx = client.post("/v1/escrow", json=make_escrow_payload(payer["id"], payee["id"])).json()

    dispute_payload = {
        "opened_by_agent_id": payer["id"],
        "reason": "The task was not completed as described in the agreement",
    }
    resp = client.post(f"/v1/escrow/{tx['id']}/dispute", json=dispute_payload)
    assert resp.status_code == 400


def test_open_duplicate_dispute(client, ed25519_keypair, second_keypair):
    payer = create_agent(client, ed25519_keypair)
    payee = create_agent(client, second_keypair)
    tx = client.post("/v1/escrow", json=make_escrow_payload(payer["id"], payee["id"])).json()

    mock_intent = {"id": f"pi_{uuid4().hex}"}
    with patch("stripe.PaymentIntent.create", return_value=mock_intent):
        client.post(f"/v1/escrow/{tx['id']}/fund")

    dispute_payload = {
        "opened_by_agent_id": payer["id"],
        "reason": "The task was not completed as described in the agreement",
    }
    client.post(f"/v1/escrow/{tx['id']}/dispute", json=dispute_payload)
    # Second dispute fails — escrow is now in DISPUTED status (400) rather than 409
    resp = client.post(f"/v1/escrow/{tx['id']}/dispute", json=dispute_payload)
    assert resp.status_code in (400, 409)


# ── Fee calculation ───────────────────────────────────────────────────────────

def test_fee_below_threshold():
    from app.services.escrow import calculate_fee
    fee = calculate_fee(Decimal("500.00"), Decimal("0.00"))
    assert fee == Decimal("0.00")


def test_fee_above_threshold():
    from app.services.escrow import calculate_fee
    # payer has $9,900 cumulative, adding $500 → $400 is above threshold
    fee = calculate_fee(Decimal("500.00"), Decimal("9900.00"))
    assert fee == Decimal("6.00")  # 1.5% of $400


def test_fee_fully_above_threshold():
    from app.services.escrow import calculate_fee
    # payer already over threshold, full amount is taxable
    fee = calculate_fee(Decimal("1000.00"), Decimal("15000.00"))
    assert fee == Decimal("15.00")  # 1.5% of $1,000
