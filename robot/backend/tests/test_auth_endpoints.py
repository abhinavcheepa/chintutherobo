import time
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.server import app, ws_tickets, clean_expired_tickets, TICKET_TTL_S, ticket_request_history
from backend.config import AUTH_TOKEN


@pytest.fixture
def client():
    # Use an allowed host so TrustedHostMiddleware permits requests
    return TestClient(app, base_url="http://testserver")


def test_health_endpoint_no_auth(client):
    """Health check endpoint must be publicly accessible without authentication."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "time" in data


def test_rest_endpoints_require_bearer_auth(client):
    """Protected REST endpoints must refuse requests without valid Bearer credentials."""
    # /api/telemetry/latest
    res_no_auth = client.get("/api/telemetry/latest")
    assert res_no_auth.status_code == 401

    res_bad_auth = client.get("/api/telemetry/latest", headers={"Authorization": "Bearer bad-token"})
    assert res_bad_auth.status_code == 401

    # /api/system/info
    res_info_no_auth = client.get("/api/system/info")
    assert res_info_no_auth.status_code == 401

    res_info_bad_auth = client.get("/api/system/info", headers={"Authorization": "Bearer wrong-token"})
    assert res_info_bad_auth.status_code == 401

    # /api/system/info with valid auth
    res_info_valid = client.get("/api/system/info", headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    assert res_info_valid.status_code == 200
    assert "environment" in res_info_valid.json()
    assert "serial_connected" in res_info_valid.json()


def test_ws_ticket_generation_and_consumption(client):
    """Verify single-use ticket lifecycle: creation, consumption, and replay rejection."""
    # 1. Reject without auth
    res = client.post("/api/ws-ticket")
    assert res.status_code == 401

    # 2. Reject with invalid auth
    res = client.post("/api/ws-ticket", headers={"Authorization": "Bearer invalid_secret"})
    assert res.status_code == 401

    # 3. Create ticket with valid auth
    res = client.post("/api/ws-ticket", headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    assert res.status_code == 200
    data = res.json()
    assert "ticket" in data
    assert data["expires_in"] == 30
    ticket = data["ticket"]

    # 4. Connect with single-use ticket
    with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection_ack"

    # 5. Replay attack: Reusing the same ticket must fail immediately
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008


def test_ws_rejects_legacy_token_query_param(client):
    """Verify that passing ?token= is strictly rejected with policy violation (1008)."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws?token={AUTH_TOKEN}") as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008


def test_ws_rejects_missing_ticket(client):
    """Connecting to /ws without a ticket must fail."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008


def test_ws_rejects_expired_ticket(client):
    """Expired tickets must be cleaned up and rejected."""
    # Create ticket
    res = client.post("/api/ws-ticket", headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    assert res.status_code == 200
    ticket = res.json()["ticket"]

    # Manually backdate ticket expiry
    ws_tickets[ticket] = time.time() - 5.0

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008


def test_ws_ticket_capacity_limit(client):
    """Verify that outstanding tickets cannot exceed the cap of 8."""
    ws_tickets.clear()
    ticket_request_history.clear()
    tickets = []
    try:
        # Issue up to 8 tickets
        for _ in range(8):
            res = client.post("/api/ws-ticket", headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
            assert res.status_code == 200
            tickets.append(res.json()["ticket"])

        # 9th ticket must be rejected with 429 Too Many Requests
        res_overflow = client.post("/api/ws-ticket", headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
        assert res_overflow.status_code == 429
    finally:
        ws_tickets.clear()


def test_trusted_host_middleware_blocks_unauthorized_host():
    """Requests with unknown Host headers must be blocked by TrustedHostMiddleware."""
    rogue_client = TestClient(app, base_url="http://malicious-attacker.com")
    res = rogue_client.get("/api/health")
    assert res.status_code == 400
