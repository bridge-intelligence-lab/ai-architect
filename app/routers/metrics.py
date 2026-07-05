"""Metrics and health endpoints: Prometheus /metrics and /healthz."""

import os

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.utils.metrics import registry

router = APIRouter()

# Optional token-based protection for /metrics
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "").strip()


@router.get("/healthz")
def healthz():
    """Liveness check: returns ok when the process is up."""
    return {"status": "ok"}


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    responses={
        200: {
            "content": {
                "text/plain": {"schema": {"type": "string"}},
            }
        }
    },
)
def metrics(
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token")
):
    """Prometheus metrics export (text/plain). Token required if METRICS_TOKEN env set."""
    # If a token is configured, enforce it; otherwise allow open access
    if METRICS_TOKEN:
        if not x_metrics_token or x_metrics_token != METRICS_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="forbidden"
            )
    data = generate_latest(registry)
    # Keep precise Prometheus content type for runtime; OpenAPI will still advertise text/plain
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
