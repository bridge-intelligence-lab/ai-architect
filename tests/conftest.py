import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

# Modern MLflow refuses the local file store unless explicitly allowed; CI sets
# this in the workflow env, local runs get it here so the training subprocess
# can't stall or crash on the file-store guard.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

# A hung training subprocess should fail the test, not freeze the whole run.
TRAIN_TIMEOUT_SECONDS = 180


@pytest.fixture(scope="session")
def trained_model(tmp_path_factory):
    """Run ml/train.py once per session and share the tracking store.

    Training the tiny synthetic model is deterministic, so every test that
    needs "a trained model exists" can reuse this store instead of paying
    for its own subprocess run.
    """
    uri = str(tmp_path_factory.mktemp("mlflow") / ".mlruns")
    experiment = "ai-architect-test"
    env = dict(
        os.environ,
        MLFLOW_TRACKING_URI=uri,
        MLFLOW_EXPERIMENT_NAME=experiment,
    )
    result = subprocess.run(
        [sys.executable, "ml/train.py"],
        capture_output=True,
        text=True,
        env=env,
        timeout=TRAIN_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, (
        f"session training failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return SimpleNamespace(uri=uri, experiment=experiment, result=result)


@pytest.fixture
def model_env(trained_model, monkeypatch):
    """Point the app at the session-trained MLflow store."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", trained_model.uri)
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", trained_model.experiment)
    return trained_model
