"""Prediction endpoints: ML model inference with feature validation."""

import os
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.predict import PredictRequest, PredictResponse
from app.services.mlflow_client import MLflowClientWrapper
from app.utils.audit import make_hash, write_audit
from app.utils.cost import estimate_tokens_and_cost
from app.utils.rbac import require_role
from db.session import get_session, init_db

router = APIRouter()


@router.get("/predict/schema", response_model=dict)
def get_predict_schema(role: str = Depends(require_role("analyst"))):
    """Retrieve expected feature order and model metadata from latest MLflow run.

    Requires analyst role."""
    client = MLflowClientWrapper()
    try:
        _model, run_id, _model_uri = client.load_latest_model()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"model load failed: {e}")
    features = client.get_feature_order(run_id=run_id) or []
    return {"features": features, "run_id": run_id, "experiment": client.get_experiment_name()}


@router.post("/predict", response_model=PredictResponse)
def post_predict(
    req: Request, payload: PredictRequest, role: str = Depends(require_role("analyst"))
):
    """Generate model prediction for provided features with validation against schema.

    Requires analyst role. Enforces exact feature match to training set."""
    start = time.perf_counter()

    if not isinstance(payload.features, dict) or not payload.features:
        raise HTTPException(
            status_code=400, detail="features must be a non-empty object"
        )

    client = MLflowClientWrapper()
    try:
        model, run_id, model_uri = client.load_latest_model()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"model load failed: {e}")

    # Prepare features: enforce expected order/signature when available
    try:
        import numpy as np

        x = payload.features
        # First, validate that provided values are numeric-like to surface clear errors
        conv = {}
        for k, v in x.items():
            try:
                conv[k] = float(v) if v is not None else 0.0
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"prediction failed: {e}")

        # Attempt to load training feature order; fallback to sorted keys
        feature_order = client.get_feature_order(run_id=run_id)
        if feature_order:
            # Validate exact match: no missing/extra features
            provided = set(x.keys())
            expected = set(feature_order)
            missing = sorted(list(expected - provided))
            extra = sorted(list(provided - expected))
            if missing or extra:
                msg = []
                if missing:
                    msg.append(f"missing features: {missing}")
                if extra:
                    msg.append(f"unknown features: {extra}")
                raise HTTPException(status_code=400, detail="; ".join(msg))
            keys = feature_order
        else:
            keys = sorted(x.keys())
        vals = [conv.get(k, 0.0) for k in keys]
        arr = np.array(vals).reshape(1, -1)
        pred = model.predict(arr)[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"prediction failed: {e}")

    # Audit + cost
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    tp, tc, cost = estimate_tokens_and_cost(
        model=model_name, prompt=str(payload.features), completion=str(pred)
    )

    latency_ms = int((time.perf_counter() - start) * 1000)
    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "user_id": payload.user_id,
        "endpoint": "/predict",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tokens_prompt": tp,
        "tokens_completion": tc,
        "cost_usd": round(cost, 6),
        "latency_ms": latency_ms,
        "compliance_flag": False,
        "prompt_hash": make_hash(str(payload.features)),
        "response_hash": make_hash(str(pred)),
        "model_run_id": run_id,
        "model_experiment": client.get_experiment_name(),
        "model_uri": model_uri,
    }

    try:
        init_db()
    except Exception:
        pass
    db = get_session()
    try:
        write_audit(
            db,
            request_id=audit["request_id"],
            endpoint=audit["endpoint"],
            user_id=audit["user_id"],
            tokens_prompt=audit["tokens_prompt"],
            tokens_completion=audit["tokens_completion"],
            cost_usd=audit["cost_usd"],
            latency_ms=audit["latency_ms"],
            compliance_flag=audit["compliance_flag"],
            prompt_hash=audit["prompt_hash"],
            response_hash=audit["response_hash"],
        )
    finally:
        db.close()

    return PredictResponse(
        prediction=str(pred),
        model_version=run_id,
        metrics={},
        audit=audit,
    )
