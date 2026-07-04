from fastapi.testclient import TestClient

from app.main import app


def test_predict_after_train(model_env):
    client = TestClient(app)
    # Features: we don't know the exact order; our predict sorts keys alphabetically
    payload = {
        "features": {
            "f0": 0.1,
            "f1": -0.2,
            "f2": 0.3,
            "f3": 0.0,
            "f4": 0.2,
            "f5": -0.1,
            "f6": 0.0,
            "f7": 0.0,
        }
    }
    r = client.post("/predict", json=payload, headers={"X-User-Role": "analyst"})
    assert r.status_code == 200
    data = r.json()
    assert "prediction" in data
    assert data["model_version"]
    assert "audit" in data
