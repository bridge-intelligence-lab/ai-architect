"""Export a chat session from short-term memory to a dated Markdown transcript.

Intended for evaluation work: capture what the assistant actually said, in a form
you can annotate later, without grading it in the moment.

    python scripts/export_session.py --list        # recent sessions
    python scripts/export_session.py               # most recent non-eval session
    python scripts/export_session.py --session S   # a specific session
    python scripts/export_session.py --out-dir ~/notes/experiments

Sessions whose id starts with "eval-" are skipped by default: those are harness
runs, not real conversations, and they would drown the real ones. Pass
--include-eval to keep them.

Reads MEMORY_DB_PATH, the same variable the app uses (app/memory/short_memory.py).
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = "./data/memory_short.db"
DEFAULT_OUT = "./experiments"
EVAL_PREFIX = "eval-"


def connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        sys.exit(f"memory db not found: {db_path} (set MEMORY_DB_PATH)")
    # read-only: exporting must never mutate the memory the app is using
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _eval_clause(include_eval: bool) -> str:
    return "" if include_eval else " WHERE session_id NOT LIKE ?"


def _eval_params(include_eval: bool) -> tuple:
    return () if include_eval else (f"{EVAL_PREFIX}%",)


def list_sessions(conn: sqlite3.Connection, include_eval: bool, limit: int) -> None:
    rows = conn.execute(
        "SELECT session_id, COUNT(*) turns, MIN(timestamp) started, MAX(timestamp) ended"
        f" FROM turns{_eval_clause(include_eval)}"
        " GROUP BY session_id ORDER BY ended DESC LIMIT ?",
        (*_eval_params(include_eval), limit),
    ).fetchall()
    if not rows:
        print("no sessions found")
        return
    print(f"{'session_id':<40} {'turns':>5}  started              ended")
    for r in rows:
        print(f"{r['session_id']:<40} {r['turns']:>5}  {r['started']}  {r['ended']}")


def latest_session(conn: sqlite3.Connection, include_eval: bool) -> str:
    row = conn.execute(
        f"SELECT session_id FROM turns{_eval_clause(include_eval)}"
        " ORDER BY timestamp DESC LIMIT 1",
        _eval_params(include_eval),
    ).fetchone()
    if row is None:
        sys.exit("no session found")
    return row["session_id"]


def export(conn: sqlite3.Connection, session_id: str, out_dir: Path) -> Path:
    turns = conn.execute(
        "SELECT role, content, timestamp FROM turns WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    if not turns:
        sys.exit(f"session not found: {session_id}")

    day = max(t["timestamp"] for t in turns)[:10]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{day}-{session_id}.md"

    lines = [
        "---",
        "tags: [experiment, transcript]",
        f"session: {session_id}",
        f"captured_day: {day}",
        "status: raw",
        "---",
        "",
        f"# Session transcript — {day}",
        "",
        f"> Session `{session_id}`. Raw, captured for later evaluation."
        " Add a **Notes** line under any turn that surprised you or felt wrong.",
        "",
    ]
    for t in turns:
        clock = (t["timestamp"] or "")[11:19]
        lines.append(f"### [{clock}] {(t['role'] or '').upper()}")
        lines.append(t["content"] or "")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session", help="session id (default: most recent)")
    ap.add_argument("--list", action="store_true", help="list recent sessions and exit")
    ap.add_argument("--include-eval", action="store_true", help="include eval-* sessions")
    ap.add_argument("--limit", type=int, default=15, help="rows for --list (default 15)")
    ap.add_argument(
        "--out-dir",
        default=os.getenv("OUT_DIR", DEFAULT_OUT),
        help=f"transcript output directory (default {DEFAULT_OUT})",
    )
    args = ap.parse_args()

    conn = connect(Path(os.getenv("MEMORY_DB_PATH", DEFAULT_DB)))
    try:
        if args.list:
            list_sessions(conn, args.include_eval, args.limit)
            return
        session_id = args.session or latest_session(conn, args.include_eval)
        print(f"wrote: {export(conn, session_id, Path(args.out_dir).expanduser())}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
