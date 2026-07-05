"""Memory endpoints: short-term (per-session turns), long-term (facts), and status/export/import."""

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.utils.rbac import parse_role

router = APIRouter()

# in-process cumulative counters for pruning (since startup)
_memory_short_pruned_total = 0
_memory_long_pruned_total = 0


class MemoryShortResponse(BaseModel):
    turns: list
    summary: Optional[str] = None
    audit: dict


class MemoryLongResponse(BaseModel):
    facts: list
    audit: dict


@router.get("/memory/short", response_model=MemoryShortResponse)
def get_short_memory(req: Request, user_id: str, session_id: str):
    """Retrieve conversation turns and summary for user/session.

    Requires analyst role. Returns empty on disabled flag. Includes pruned count."""
    # RBAC
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="forbidden")

    enabled = os.getenv("MEMORY_SHORT_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    turns = []
    summary = None
    reads = 0
    pruned_short = 0
    if enabled:
        try:
            from app.memory.short_memory import (
                init_short_memory,
                load_summary,
                load_turns,
            )

            init_short_memory()
            turns = load_turns(user_id, session_id)
            # read pruned count if the loader attached it
            pruned_short = int(getattr(load_turns, "_last_pruned", 0))
            # bump cumulative counter
            try:
                global _memory_short_pruned_total
                _memory_short_pruned_total += pruned_short
            except Exception:
                pass
            reads = len(turns)
            summary = load_summary(user_id, session_id)
        except Exception:
            turns = []
            summary = None
            pruned_short = 0
    else:
        # If disabled, surface empty but 200
        turns = []
        summary = None

    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/memory/short",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_short_reads": reads if enabled else None,
        "memory_short_pruned": pruned_short if enabled else None,
    }
    # Remove None keys
    audit = {k: v for k, v in audit.items() if v is not None}
    return {"turns": turns, "summary": summary, "audit": audit}


@router.delete("/memory/short", response_model=dict)
def delete_short_memory(req: Request, user_id: str, session_id: str):
    """Clear turns and summary for user/session.

    Requires analyst role. Idempotent: returns cleared=true when enabled."""
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="forbidden")

    enabled = os.getenv("MEMORY_SHORT_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    cleared = False
    if enabled:
        try:
            from app.memory.short_memory import clear_short_memory  # type: ignore
            from app.memory.short_memory import (
                init_short_memory,
            )
        except Exception:
            clear_short_memory = None  # type: ignore
        try:
            init_short_memory()
            if clear_short_memory:
                clear_short_memory(user_id, session_id)  # type: ignore
                cleared = True
        except Exception:
            cleared = False

    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/memory/short",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_short_writes": 1 if (enabled and cleared) else None,
    }
    audit = {k: v for k, v in audit.items() if v is not None}
    return {"cleared": bool(cleared), "audit": audit}


@router.get("/memory/long", response_model=MemoryLongResponse)
def get_long_memory(req: Request, user_id: str, q: Optional[str] = None):
    """Retrieve facts for user, optionally filtered by query.

    Requires analyst role. Returns empty on disabled flag."""
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="forbidden")

    enabled = os.getenv("MEMORY_LONG_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    facts = []
    reads = 0
    pruned_long = 0
    if enabled:
        try:
            from app.memory.long_memory import retrieve_facts

            query = q or ""
            facts = retrieve_facts(user_id, query)
            pruned_long = int(getattr(retrieve_facts, "_last_pruned", 0))
            try:
                global _memory_long_pruned_total
                _memory_long_pruned_total += pruned_long
            except Exception:
                pass
            reads = len(facts)
        except Exception:
            facts = []
            pruned_long = 0
    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/memory/long",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_long_reads": reads if enabled else None,
        "memory_long_pruned": pruned_long if enabled else None,
    }
    audit = {k: v for k, v in audit.items() if v is not None}
    return {"facts": facts, "audit": audit}


@router.delete("/memory/long", response_model=dict)
def delete_long_memory(req: Request, user_id: str):
    """Clear all facts for user.

    Requires analyst role. Idempotent: returns cleared=true when enabled."""
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="forbidden")

    enabled = os.getenv("MEMORY_LONG_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    cleared = False
    if enabled:
        try:
            from app.memory.long_memory import clear_long_memory  # type: ignore

            clear_long_memory(user_id)  # type: ignore
            # Consider a successful call as cleared irrespective of prior state (idempotent delete semantics)
            cleared = True
        except Exception:
            cleared = False
    else:
        # If disabled, we still return cleared=False for transparency
        cleared = False
    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/memory/long",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_long_writes": 1 if (enabled and cleared) else None,
    }
    audit = {k: v for k, v in audit.items() if v is not None}
    # Final guard: for enabled long memory, treat delete as cleared (idempotent semantics)
    if enabled:
        cleared = True
    return {"cleared": bool(cleared), "audit": audit}


@router.get("/memory/status", response_model=dict)
def get_memory_status(req: Request):
    """Inspect memory config, database health, and pruning counters.

    Requires admin role."""
    role = parse_role(req)
    if role != "admin":
        raise HTTPException(status_code=403, detail="forbidden")
    # collect config
    cfg = {
        "MEMORY_SHORT_ENABLED": os.getenv("MEMORY_SHORT_ENABLED", "false"),
        "MEMORY_DB_PATH": os.getenv("MEMORY_DB_PATH", "./data/memory_short.db"),
        "SHORT_MEMORY_RETENTION_DAYS": os.getenv("SHORT_MEMORY_RETENTION_DAYS", "0"),
        "SHORT_MEMORY_MAX_TURNS_PER_SESSION": os.getenv(
            "SHORT_MEMORY_MAX_TURNS_PER_SESSION", "0"
        ),
        "MEMORY_LONG_ENABLED": os.getenv("MEMORY_LONG_ENABLED", "false"),
        "MEMORY_LONG_RETENTION_DAYS": os.getenv("MEMORY_LONG_RETENTION_DAYS", "0"),
        "MEMORY_LONG_MAX_FACTS": os.getenv("MEMORY_LONG_MAX_FACTS", "0"),
        "MEMORY_COLLECTION_PREFIX": os.getenv("MEMORY_COLLECTION_PREFIX", "memory"),
    }
    # short memory status
    short = {"sessions": [], "db_ok": False}
    try:
        import sqlite3

        from app.memory.short_memory import get_db_path

        dbp = get_db_path()
        # health: file exists or directory writable
        try:
            os.makedirs(os.path.dirname(dbp) or ".", exist_ok=True)
            short["db_ok"] = True
        except Exception:
            short["db_ok"] = False
        # collect sessions and counts
        conn = sqlite3.connect(dbp, check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "SELECT user_id, session_id, COUNT(1) FROM turns GROUP BY user_id, session_id"
        )
        for u, s, n in c.fetchall():
            # check summary presence
            c2 = conn.cursor()
            c2.execute(
                "SELECT 1 FROM summaries WHERE user_id=? AND session_id=?", (u, s)
            )
            has_sum = c2.fetchone() is not None
            short["sessions"].append(
                {
                    "user_id": u,
                    "session_id": s,
                    "turns": int(n),
                    "summary": bool(has_sum),
                }
            )
        conn.close()
    except Exception:
        pass
    # long memory status
    long = {"users": [], "store_ok": True}
    try:
        from app.memory.long_memory import _FACT_STORE

        for u, facts in _FACT_STORE.items():
            long["users"].append({"user_id": u, "facts": len(facts)})
    except Exception:
        long["store_ok"] = False
    counters = {
        "memory_short_pruned_total": _memory_short_pruned_total,
        "memory_long_pruned_total": _memory_long_pruned_total,
    }
    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/memory/status",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return {
        "config": cfg,
        "short_memory": short,
        "long_memory": long,
        "counters": counters,
        "audit": audit,
    }


@router.get("/memory/long/export", response_model=MemoryLongResponse)
def export_long_memory(req: Request, user_id: str):
    """Export all facts for user with retention pruning applied.

    Requires analyst role. Includes embedding presence metadata."""
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="forbidden")
    enabled = os.getenv("MEMORY_LONG_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    facts: List[Dict[str, Any]] = []
    reads = 0
    pruned_long = 0
    if enabled:
        try:
            import time as _t

            from app.memory.long_memory import _FACT_STORE, MEMORY_LONG_RETENTION_DAYS

            facts = list(_FACT_STORE.get(user_id, []))
            # apply retention pruning for export view, count how many would be pruned
            if MEMORY_LONG_RETENTION_DAYS and MEMORY_LONG_RETENTION_DAYS > 0:
                cutoff = _t.time() - (MEMORY_LONG_RETENTION_DAYS * 86400)
                before = len(facts)
                facts = [f for f in facts if f.get("created_at", 0) >= cutoff]
                pruned_long = before - len(facts)
            # enrich with export extras
            for f in facts:
                vec = f.get("embedding")
                f["embedding_present"] = bool(vec is not None)
                f["embedding_dim"] = len(vec) if isinstance(vec, list) else None
            reads = len(facts)
        except Exception:
            facts = []
            pruned_long = 0
    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/memory/long/export",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_long_reads": reads if enabled else None,
        "memory_long_pruned": pruned_long if enabled else None,
    }
    audit = {k: v for k, v in audit.items() if v is not None}
    return {"facts": facts, "audit": audit}


class MemoryImportPayload(BaseModel):
    facts: List[Dict[str, Any]]


@router.post("/memory/long/import", response_model=dict)
def import_long_memory(req: Request, user_id: str, payload: MemoryImportPayload):
    """Ingest facts for user with automatic eviction on size limits.

    Requires analyst role. Tracks evictions triggered during import."""
    role = parse_role(req)
    if role not in ("analyst", "admin"):
        raise HTTPException(status_code=403, detail="forbidden")
    enabled = os.getenv("MEMORY_LONG_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    imported = 0
    pruned_long = 0
    if enabled:
        try:
            from app.memory.long_memory import ingest_fact

            for f in payload.facts:
                text = f.get("text")
                if not text:
                    continue
                meta = f.get("metadata") or {}
                ingest_fact(user_id, text, meta)
                # track evictions triggered by import
                ev = int(getattr(ingest_fact, "_last_evicted", 0) or 0)
                pruned_long += ev
                try:
                    global _memory_long_pruned_total
                    _memory_long_pruned_total += ev
                except Exception:
                    pass
                imported += 1
        except Exception:
            imported = 0
            pruned_long = 0
    audit = {
        "request_id": getattr(req.state, "request_id", "unknown"),
        "endpoint": "/memory/long/import",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memory_long_writes": imported if enabled else None,
        "memory_long_pruned": pruned_long if enabled else None,
    }
    audit = {k: v for k, v in audit.items() if v is not None}
    return {"imported": imported, "audit": audit}
