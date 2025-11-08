import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Callable

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .routers.memory import router as memory_router
from .routers.metrics import router as metrics_router
from .routers.pii import router as pii_router
from .routers.pii_remediation import router as pii_remediation_router
from .routers.architect import router as architect_router
from .routers.architect_ui import router as architect_ui_router
from .routers.architect_stream import router as architect_stream_router
from .routers.ui import router as unified_ui_router
from .routers.policy import router as policy_router
from .routers.predict import router as predict_router
from .routers.query import router as query_router
from .routers.research import router as research_router
from .routers.think import router as think_router
from .routers.risk import router as risk_router
from .utils.logger import get_logger
from .utils.metrics import request_count, request_latency

# Load .env normally first
load_dotenv()
# In local env, force .env to override any pre-set environment (e.g., VS Code injected)
if os.getenv("APP_ENV", "local").lower() == "local":
    load_dotenv(find_dotenv(), override=True)

APP_ENV = os.getenv("APP_ENV", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REQUEST_ID_HEADER = os.getenv("REQUEST_ID_HEADER", "X-Request-ID")

logger = get_logger(level=LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log resolved LLM provider/model early for diagnostics
    resolved_provider = (os.getenv("LLM_PROVIDER", "stub") or "stub").lower()
    resolved_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    logger.info({"event": "startup", "env": APP_ENV, "llm_provider": resolved_provider, "llm_model": resolved_model})
    # Initialize DB tables
    try:
        from db.session import init_db

        init_db()
    except Exception as e:
        logger.error({"event": "db_init_error", "error": str(e)})
    yield
    logger.info({"event": "shutdown"})


app = FastAPI(title="AI Architect", version="0.1.0", lifespan=lifespan)

# Exception handlers
from .utils.exceptions import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next: Callable):
    start = time.perf_counter()
    req_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
    # Attach to request state for downstream
    request.state.request_id = req_id

    response: Response = Response(status_code=500)
    endpoint = request.url.path
    try:
        response = await call_next(request)
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.error(
            {
                "event": "request_error",
                "method": request.method,
                "path": endpoint,
                "error": str(e),
                "request_id": req_id,
                "latency_ms": duration_ms,
            }
        )
        if endpoint != "/metrics":
            request_count.labels(endpoint=endpoint, status="500").inc()
            request_latency.labels(endpoint=endpoint).observe(duration_ms / 1000.0)
        raise
    else:
        duration_ms = int((time.perf_counter() - start) * 1000)
        if endpoint != "/metrics":
            request_count.labels(
                endpoint=endpoint, status=str(response.status_code)
            ).inc()
            request_latency.labels(endpoint=endpoint).observe(duration_ms / 1000.0)
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            {
                "event": "request",
                "method": request.method,
                "path": endpoint,
                "status_code": getattr(response, "status_code", -1),
                "request_id": req_id,
                "latency_ms": duration_ms,
            }
        )
        response.headers[REQUEST_ID_HEADER] = req_id
    return response


# Routers
app.include_router(metrics_router)
app.include_router(query_router)
app.include_router(research_router)
app.include_router(predict_router)
app.include_router(pii_router)
app.include_router(risk_router)
app.include_router(memory_router)
app.include_router(policy_router)
app.include_router(pii_remediation_router)
app.include_router(architect_router)
app.include_router(architect_stream_router)
app.include_router(architect_ui_router)
app.include_router(unified_ui_router)
app.include_router(think_router)
