from fastapi.testclient import TestClient

from app.main import app


def test_predict_missing_feature(model_env):
    client = TestClient(app)
    # Omitting one feature from the expected set
    payload = {"features": {"f0": 0.1, "f1": 0.2, "f2": 0.3}}
    r = client.post("/predict", json=payload, headers={"X-User-Role": "analyst"})
    assert r.status_code == 400
    assert "missing features" in r.text


def test_predict_extra_feature(model_env):
    client = TestClient(app)
    # Add an extra feature not present in training
    payload = {"features": {"f0": 0.1, "f1": 0.2, "f2": 0.3, "f_extra": 1.0}}
    r = client.post("/predict", json=payload, headers={"X-User-Role": "analyst"})
    assert r.status_code == 400
    assert "unknown features" in r.text


def test_predict_shuffled_keys_ok(model_env):
    client = TestClient(app)
    # Correct set, shuffled order
    payload = {"features": {"f3": 0.0, "f1": 0.2, "f0": 0.1, "f2": -0.1, "f4": 0.0, "f5": 0.0, "f6": 0.0, "f7": 0.1}}
    r = client.post("/predict", json=payload, headers={"X-User-Role": "analyst"})
    assert r.status_code == 200
    data = r.json()
    assert "prediction" in data
