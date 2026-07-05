"""MLflow client: load models + signatures from runs, with optional caching."""
import os
import json
from typing import List, Optional

import mlflow
import mlflow.sklearn

# Recent MLflow releases put the filesystem tracking backend in maintenance mode
# and raise unless this opt-out is set. The local file store is intentional here
# (zero-setup local runs); migration to a sqlite backend is planned.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")


class MLflowClientWrapper:
    """MLflow client for model loading and metadata extraction from runs."""

    def __init__(self, tracking_uri: str | None = None, experiment: str | None = None):
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "./.mlruns"
        )
        self.experiment = experiment or os.getenv(
            "MLFLOW_EXPERIMENT_NAME", "ai-architect"
        )
        # Configurable artifact names with sensible defaults
        self.model_artifact = os.getenv("MLFLOW_MODEL_ARTIFACT_PATH", "model")
        self.feature_order_artifact = os.getenv(
            "MLFLOW_FEATURE_ORDER_ARTIFACT", "feature_order.json"
        )
        mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_experiment(self.experiment)

    def _get_latest_run_id(self) -> str:
        exp = mlflow.get_experiment_by_name(self.experiment)
        if not exp:
            raise RuntimeError("MLflow experiment not found")
        runs = mlflow.search_runs(
            exp.experiment_id, order_by=["start_time DESC"], max_results=1
        )
        if runs.empty:
            raise RuntimeError("No runs found in MLflow experiment")
        return runs.iloc[0]["run_id"]

    def _now(self) -> float:
        import time
        return time.time()

    def _cache_ttl(self) -> float:
        try:
            return float(os.getenv("MLFLOW_MODEL_CACHE_TTL", "0") or 0.0)
        except Exception:
            return 0.0

    _MODEL_CACHE: dict[str, tuple[object, float]] = {}

    def _load_model_uri(self, uri: str):
        ttl = self._cache_ttl()
        if ttl > 0:
            item = self._MODEL_CACHE.get(uri)
            if item:
                model, ts = item
                if (self._now() - ts) <= ttl:
                    return model
        model = mlflow.sklearn.load_model(uri)
        if ttl > 0:
            self._MODEL_CACHE[uri] = (model, self._now())
        return model

    def load_latest_model(self, artifact_path: str | None = None):
        """Load model from explicit MLFLOW_MODEL_URI or latest run; return (model, run_id, uri)."""
        # Prefer explicit model URI override if provided
        explicit_uri = os.getenv("MLFLOW_MODEL_URI")
        if explicit_uri:
            model = self._load_model_uri(explicit_uri)
            # Try to parse run_id from runs:/ URIs for auditing when possible
            run_id = None
            try:
                if explicit_uri.startswith("runs:/"):
                    parts = explicit_uri.split("/")
                    run_id = parts[1]  # runs:/{run_id}/...
            except Exception:
                run_id = None
            return model, (run_id or "unknown"), explicit_uri
        # Otherwise load latest run
        run_id = self._get_latest_run_id()
        apath = artifact_path or self.model_artifact
        uri = f"runs:/{run_id}/{apath}"
        model = self._load_model_uri(uri)
        return model, run_id, uri

    def get_signature_input_names(self, model_uri: str) -> Optional[List[str]]:
        """Extract model signature input column names; return None if unavailable."""
        try:
            from mlflow.models import get_model_info

            info = get_model_info(model_uri)
            sig = getattr(info, "signature", None)
            if sig and getattr(sig, "inputs", None) is not None:
                try:
                    d = sig.inputs.to_dict()  # type: ignore[attr-defined]
                    cols = d.get("inputs") or d.get("columns") or []
                    names = [c.get("name") for c in cols if isinstance(c, dict) and c.get("name")]
                    if names:
                        return names
                except Exception:
                    pass
        except Exception:
            return None
        return None

    def get_feature_order(self, run_id: Optional[str] = None) -> Optional[List[str]]:
        """Download and parse feature_order.json from run artifact; return None if unavailable."""
        try:
            rid = run_id or self._get_latest_run_id()
            artifact_uri = f"runs:/{rid}/{self.feature_order_artifact}"
            # mlflow 2.x
            from mlflow.artifacts import download_artifacts  # lazy import

            local_path = download_artifacts(artifact_uri)
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            fo = data.get("feature_order")
            if isinstance(fo, list) and all(isinstance(x, str) for x in fo):
                return fo
        except Exception:
            return None
        return None

    def get_experiment_name(self) -> str:
        """Return configured experiment name."""
        return self.experiment
