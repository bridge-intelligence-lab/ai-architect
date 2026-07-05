"""Architect UI endpoints: HTML form for architect endpoint."""

import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/architect/ui", response_class=HTMLResponse, tags=["Architect"])
def get_ui(request: Request):
    """Serve architect form HTML, gated by PROJECT_GUIDE_ENABLED flag."""
    context = {
        "project_guide_enabled": os.getenv("PROJECT_GUIDE_ENABLED", "").lower() in ("1", "true", "yes", "on"),
    }
    resp = templates.TemplateResponse(request, "architect_form.html", context)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp
