"""Short-term conversation memory: SQLite-backed turns and rolling summaries per user+session."""
import os
import sqlite3
from datetime import datetime
from typing import List, Tuple

from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_db_path() -> str:
    return os.getenv("MEMORY_DB_PATH", "./data/memory_short.db")


def get_summary_max_turns() -> int:
    return int(os.getenv("MEMORY_SHORT_MAX_TURNS", "10"))


def get_retention_days() -> int:
    return int(os.getenv("SHORT_MEMORY_RETENTION_DAYS", "0"))


def get_max_turns_per_session() -> int:
    return int(os.getenv("SHORT_MEMORY_MAX_TURNS_PER_SESSION", "0"))


def init_short_memory(db_path: str | None = None):
    path = db_path or get_db_path()
    dir_ = os.path.dirname(path) or "."
    os.makedirs(dir_, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    c = conn.cursor()
    c.execute(
        """
      CREATE TABLE IF NOT EXISTS turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        timestamp TEXT
      )
    """
    )
    c.execute(
        """
      CREATE TABLE IF NOT EXISTS summaries (
        user_id TEXT,
        session_id TEXT,
        summary TEXT,
        updated_at TEXT,
        PRIMARY KEY(user_id, session_id)
      )
    """
    )
    conn.commit()
    conn.close()


def load_turns(user_id: str, session_id: str) -> List[Tuple[str, str]]:
    """Load conversation turns for user+session, pruned by retention days and max-per-session.

    Attaches pruned count to load_turns._last_pruned for downstream visibility.
    """
    init_short_memory()
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()
    pruned = 0
    # Optional retention by days
    rd = get_retention_days()
    if rd and rd > 0:
        cutoff = datetime.utcnow().timestamp() - (rd * 86400)
        # count and delete old rows
        c.execute(
            "SELECT COUNT(1) FROM turns WHERE user_id=? AND session_id=? AND strftime('%s', timestamp) < ?",
            (user_id, session_id, int(cutoff)),
        )
        n_old = c.fetchone()[0] or 0
        if n_old:
            pruned += int(n_old)
            c.execute(
                "DELETE FROM turns WHERE user_id=? AND session_id=? AND strftime('%s', timestamp) < ?",
                (user_id, session_id, int(cutoff)),
            )
            conn.commit()
    # Optional cap per session: enforce by deleting oldest beyond cap, then select
    cap = get_max_turns_per_session()
    if cap and cap > 0:
        c.execute(
            "SELECT id FROM turns WHERE user_id=? AND session_id=? ORDER BY id DESC",
            (user_id, session_id),
        )
        ids_desc = [r[0] for r in c.fetchall()]
        if len(ids_desc) > cap:
            drop_ids = ids_desc[cap:]
            pruned += len(drop_ids)
            if drop_ids:
                qmarks = ",".join(["?"] * len(drop_ids))
                c.execute(f"DELETE FROM turns WHERE id IN ({qmarks})", drop_ids)
                conn.commit()
    # Now fetch up to cap (or all if cap disabled)
    cap = get_max_turns_per_session()
    if cap and cap > 0:
        c.execute(
            """
          SELECT role, content FROM turns
          WHERE user_id=? AND session_id=?
          ORDER BY id ASC
        """,
            (user_id, session_id),
        )
        rows = c.fetchall()
        if len(rows) > cap:
            rows = rows[-cap:]
    else:
        c.execute(
            """
          SELECT role, content FROM turns
          WHERE user_id=? AND session_id=?
          ORDER BY id ASC
        """,
            (user_id, session_id),
        )
        rows = c.fetchall()
    conn.close()
    # stash pruned count on logger for visibility (no global state)
    try:
        logger.debug(
            {
                "event": "short_memory_pruned",
                "count": pruned,
                "user_id": user_id,
                "session_id": session_id,
            }
        )
    except Exception:
        pass
    # monkeypatch: attach attribute on function for router to read (simple approach)
    load_turns._last_pruned = pruned  # type: ignore[attr-defined]
    return rows


def load_summary(user_id: str, session_id: str) -> str:
    """Retrieve stored summary for user+session; empty string if none exists."""
    init_short_memory()
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()
    c.execute(
        """
      SELECT summary FROM summaries
      WHERE user_id=? AND session_id=?
    """,
        (user_id, session_id),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""


def save_turn(user_id: str, session_id: str, role: str, content: str):
    """Store a single conversation turn (role, content) with timestamp."""
    init_short_memory()
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()
    c.execute(
        """
      INSERT INTO turns (user_id, session_id, role, content, timestamp)
      VALUES (?, ?, ?, ?, ?)
    """,
        (user_id, session_id, role, content, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def summarize_context(turns: List[Tuple[str, str]]) -> str:
    snippet = "\n".join(f"{r}: {c}" for r, c in turns)
    return snippet if len(snippet) <= 500 else snippet[-500:]


def update_summary_if_needed(user_id: str, session_id: str) -> bool:
    """Persist rolling summary if turn count exceeds threshold; return True if written."""
    turns = load_turns(user_id, session_id)
    max_turns = get_summary_max_turns()
    if len(turns) > max_turns:
        summary = summarize_context(turns[-max_turns:])
        conn = sqlite3.connect(get_db_path(), check_same_thread=False)
        c = conn.cursor()
        c.execute(
            """
          REPLACE INTO summaries(user_id, session_id, summary, updated_at)
          VALUES(?,?,?,?)
        """,
            (user_id, session_id, summary, datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
        return True
    return False


def clear_short_memory(user_id: str, session_id: str) -> None:
    """Delete all turns and summary for user+session."""
    init_short_memory()
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    c = conn.cursor()
    c.execute(
        "DELETE FROM turns WHERE user_id=? AND session_id=?", (user_id, session_id)
    )
    c.execute(
        "DELETE FROM summaries WHERE user_id=? AND session_id=?", (user_id, session_id)
    )
    conn.commit()
    conn.close()
