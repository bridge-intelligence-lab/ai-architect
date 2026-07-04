from fastapi.testclient import TestClient

from app.main import app


def test_predict_schema_after_training(model_env):
    client = TestClient(app)
    r = client.get("/predict/schema", headers={"X-User-Role": "analyst"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("features", []), list)
    assert data.get("run_id")
    assert data.get("experiment")
