from fastapi.testclient import TestClient

from app.main import app


def test_predict_rejects_empty_features(monkeypatch, tmp_path):
    # Point to empty mlruns so model loading will fail later; we validate payload first
    monkeypatch.setenv("MLFLOW_TRACKING_URI", str(tmp_path / ".mlruns"))
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "ai-architect-test")
    client = TestClient(app)

    # Empty features object
    r = client.post("/predict", json={"features": {}}, headers={"X-User-Role": "analyst"})
    assert r.status_code == 400
    assert "features must be a non-empty object" in r.text


def test_predict_rejects_non_numeric_values(model_env):
    # Trained model available so validation reaches value coercion
    client = TestClient(app)
    bad_payload = {"features": {"f0": "oops", "f1": None}}
    r = client.post("/predict", json=bad_payload, headers={"X-User-Role": "analyst"})
    assert r.status_code == 400
    assert "prediction failed" in r.text or "could not convert" in r.text
