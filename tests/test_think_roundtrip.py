import os
import json
from fastapi.testclient import TestClient


def test_think_roundtrip_smoke():
    os.environ.setdefault("APP_ENV", "test")
    from app.main import app

    client = TestClient(app)

    # Initial think
    r1 = client.post("/think", json={
        "request_type": "ThinkRequest",
        "session_id": "sess1",
        "user_id": "user1",
        "prompt": "Plan next step"
    }, headers={"X-User-Role": "analyst"})
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert "audit" in body1
    assert "plan" in body1

    # Continue with tool result
    r2 = client.post("/think", json={
        "request_type": "ToolResult",
        "session_id": "sess1",
        "user_id": "user1",
        "correlation_id": "123e4567-e89b-12d3-a456-426614174000",
        "result": {"ok": True}
    }, headers={"X-User-Role": "analyst"})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert "audit" in body2
    assert "plan" in body2
