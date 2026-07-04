#!/usr/bin/env python3
"""Run the LS-8 2x2 experiment grid: AGENT_BACKEND x LLM_MAX_TOKENS.

For each cell: rewrite .env, touch app/main.py (trips the uvicorn reloader,
whose re-import re-runs load_dotenv(override=True)), wait for /health, then
run scripts/run_langsmith_eval.py against the golden dataset. The original
.env values are restored at the end regardless of outcome.

After each cell, one run's audit.agent_backend is checked against the cell's
intended backend, so a reload that silently didn't take fails loudly instead
of producing a mislabeled experiment.

Usage:
    python scripts/run_experiment_grid.py            # all 4 cells
    python scripts/run_experiment_grid.py --cells langgraph-2048
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"
TOUCH_TARGET = REPO / "app" / "main.py"
HEALTH_URL = "http://localhost:8000/healthz"

CELLS = [
    {"backend": "builtin", "max_tokens": 1024},
    {"backend": "builtin", "max_tokens": 2048},
    {"backend": "langgraph", "max_tokens": 1024},
    {"backend": "langgraph", "max_tokens": 2048},
]


def cell_name(cell: dict) -> str:
    return f"{cell['backend']}-{cell['max_tokens']}"


def set_env_values(backend: str, max_tokens: int) -> None:
    text = ENV_FILE.read_text()
    text, n1 = re.subn(r"(?m)^AGENT_BACKEND=.*$", f"AGENT_BACKEND={backend}", text)
    text, n2 = re.subn(r"(?m)^LLM_MAX_TOKENS=.*$", f"LLM_MAX_TOKENS={max_tokens}", text)
    if n1 != 1 or n2 != 1:
        raise RuntimeError(f"expected exactly one AGENT_BACKEND/LLM_MAX_TOKENS line, got {n1}/{n2}")
    ENV_FILE.write_text(text)


def trigger_reload_and_wait(timeout_s: float = 90.0) -> None:
    TOUCH_TARGET.touch()
    time.sleep(3)  # give the reloader a moment to tear down the old worker
    deadline = time.monotonic() + timeout_s
    ok_streak = 0
    while time.monotonic() < deadline:
        try:
            if httpx.get(HEALTH_URL, timeout=3).status_code == 200:
                ok_streak += 1
                if ok_streak >= 2:  # stable across two checks
                    return
            else:
                ok_streak = 0
        except Exception:
            ok_streak = 0
        time.sleep(1.5)
    raise RuntimeError("server did not become healthy after reload")


def run_cell(cell: dict, python: str) -> str:
    prefix = f"grid-{cell_name(cell)}"
    cmd = [
        python,
        str(REPO / "scripts" / "run_langsmith_eval.py"),
        "--experiment-prefix", prefix,
        "--agent-backend", cell["backend"],
        "--max-tokens", str(cell["max_tokens"]),
    ]
    print(f"\n=== cell {cell_name(cell)} -> {prefix} ===", flush=True)
    res = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True)
    print(res.stdout[-2000:], flush=True)
    if res.returncode != 0:
        print(res.stderr[-2000:], file=sys.stderr, flush=True)
        raise RuntimeError(f"cell {cell_name(cell)} failed")
    m = re.search(r"experiment: (\S+)", res.stdout)
    return m.group(1) if m else prefix


def verify_cell_backend(experiment: str, expected_backend: str) -> None:
    from langsmith import Client
    from langsmith.utils import LangSmithNotFoundError

    client = Client()
    # The experiment project can lag behind the evaluate() return
    # (read-after-write); retry before treating it as missing.
    runs = []
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            runs = list(client.list_runs(project_name=experiment, is_root=True, limit=3))
            if runs:
                break
        except LangSmithNotFoundError:
            pass
        time.sleep(10)
    for run in runs:
        actual = ((run.outputs or {}).get("audit") or {}).get("agent_backend")
        if actual and actual != expected_backend:
            raise RuntimeError(
                f"experiment {experiment}: audit.agent_backend={actual!r}, "
                f"expected {expected_backend!r} — reload did not take"
            )
        if actual:
            print(f"verified: {experiment} ran on agent_backend={actual}", flush=True)
            return
    print(f"warning: {experiment} had no audit backend to verify", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells", nargs="*", help="subset, e.g. langgraph-2048")
    args = parser.parse_args()

    cells = [c for c in CELLS if not args.cells or cell_name(c) in args.cells]
    if not cells:
        print("no matching cells", file=sys.stderr)
        return 1

    python = sys.executable
    original = ENV_FILE.read_text()
    results: dict = {}
    try:
        for cell in cells:
            set_env_values(cell["backend"], cell["max_tokens"])
            trigger_reload_and_wait()
            experiment = run_cell(cell, python)
            verify_cell_backend(experiment, cell["backend"])
            results[cell_name(cell)] = experiment
    finally:
        ENV_FILE.write_text(original)
        try:
            trigger_reload_and_wait()
            print("\n.env restored to original values, server reloaded", flush=True)
        except Exception as exc:
            print(f"\n.env restored, but reload check failed: {exc}", file=sys.stderr, flush=True)

    print("\n=== grid complete ===")
    for name, exp in results.items():
        print(f"{name}: {exp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
