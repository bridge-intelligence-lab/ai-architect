"""UI endpoints: HTML forms for architect, query, and research endpoints."""

from typing import List, Optional
import os

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import requests

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

DEFAULT_STEPS: List[str] = ["search", "fetch", "summarize", "risk_check"]


def _api_url() -> str:
    port = os.getenv("PORT", "8000")
    return f"http://localhost:{port}"


@router.get("/ui", response_class=HTMLResponse, tags=["UI"])
def get_ui(request: Request):
    """Serve tabbed UI form (architect/query/research); default tab from query param."""
    # Read optional tab query param
    tab = request.query_params.get("tab") or "architect"
    if tab not in ("architect", "query", "research"):
        tab = "architect"
    return templates.TemplateResponse(
        "ui.html",
        {
            "request": request,
            "active": tab,
            "project_guide_enabled": os.getenv("PROJECT_GUIDE_ENABLED", "").lower()
            in ("1", "true", "yes", "on"),
            "steps": DEFAULT_STEPS,
        },
    )


@router.post("/ui/architect", response_class=HTMLResponse, tags=["UI"])
def ui_architect(
    request: Request,
    question: str = Form(..., min_length=3),
    mode: str = Form(...),
    grounded: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
):
    """Form handler: POST question to /architect and render UI with response."""
    payload = {"question": question, "mode": mode}
    headers = {"Content-Type": "application/json"}
    if role:
        headers["X-User-Role"] = role
    if mode == "brainstorm":
        payload["grounded"] = True if grounded == "on" else False

    resp = requests.post(f"{_api_url()}/architect", json=payload, headers=headers)
    return templates.TemplateResponse(
        "ui.html",
        {
            "request": request,
            "active": "architect",
            "architect": {"status": resp.status_code, "data": _safe_json(resp)},
            "project_guide_enabled": os.getenv("PROJECT_GUIDE_ENABLED", "").lower()
            in ("1", "true", "yes", "on"),
            "steps": DEFAULT_STEPS,
        },
    )


@router.post("/ui/query", response_class=HTMLResponse, tags=["UI"])
def ui_query(
    request: Request,
    question: str = Form(..., min_length=1),
    grounded: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
):
    """Form handler: POST question to /query and render UI with response."""
    payload = {"question": question, "grounded": grounded == "on"}
    headers = {"Content-Type": "application/json"}
    if role:
        headers["X-User-Role"] = role

    resp = requests.post(f"{_api_url()}/query", json=payload, headers=headers)
    return templates.TemplateResponse(
        "ui.html",
        {
            "request": request,
            "active": "query",
            "query": {"status": resp.status_code, "data": _safe_json(resp)},
            "project_guide_enabled": os.getenv("PROJECT_GUIDE_ENABLED", "").lower()
            in ("1", "true", "yes", "on"),
            "steps": DEFAULT_STEPS,
        },
    )


@router.post("/ui/research", response_class=HTMLResponse, tags=["UI"])
def ui_research(
    request: Request,
    topic: str = Form(..., min_length=1),
    steps: List[str] = Form(DEFAULT_STEPS),
    role: Optional[str] = Form(None),
):
    """Form handler: POST topic and steps to /research and render UI with response."""
    payload = {"topic": topic, "steps": steps}
    headers = {"Content-Type": "application/json"}
    if role:
        headers["X-User-Role"] = role

    resp = requests.post(f"{_api_url()}/research", json=payload, headers=headers)
    return templates.TemplateResponse(
        "ui.html",
        {
            "request": request,
            "active": "research",
            "research": {"status": resp.status_code, "data": _safe_json(resp)},
            "project_guide_enabled": os.getenv("PROJECT_GUIDE_ENABLED", "").lower()
            in ("1", "true", "yes", "on"),
            "steps": DEFAULT_STEPS,
        },
    )


def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"error": resp.text}
