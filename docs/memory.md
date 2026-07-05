---
title: Memory (Phase 7)
status: current
module: memory
last_reviewed: 2026-07-04
source:
  - app/memory/short_memory.py
  - app/memory/long_memory.py
---

# Memory (Phase 7)

This service supports short-term conversation memory and long-term semantic memory.

## Short-term memory (SQLite-like persistence)

- Controlled by MEMORY_SHORT_ENABLED (default false)
- Stores per user_id + session_id turns: role, content, timestamp
- When turns exceed MEMORY_SHORT_MAX_TURNS (default 10), updates rolling summary
- Audit counters: memory_short_reads, memory_short_writes, summary_updated, memory_short_pruned
- Retention controls (optional):
  - SHORT_MEMORY_RETENTION_DAYS: prune turns older than N days on read (default 0 = disabled)
  - SHORT_MEMORY_MAX_TURNS_PER_SESSION: cap turns per session, evicting oldest beyond N (default 0 = disabled)

## Long-term memory (in-process semantic store)

- Controlled by MEMORY_LONG_ENABLED (default false)
- Uses a lightweight in-memory store keyed by user_id, with optional embeddings for relevance
- Functions: ingest facts from answers; retrieve facts to augment question context
- Each fact tracks created_at (epoch seconds)
- Retention/eviction (optional):
  - MEMORY_LONG_RETENTION_DAYS: drop facts older than N days (default 0 = disabled)
  - MEMORY_LONG_MAX_FACTS: keep at most N most recent facts per user (default 0 = disabled)
- Audit counters: memory_long_reads, memory_long_writes, memory_long_pruned

## Integration in /query

- Optional session_id accepted in payload
- When enabled, recent turns/summary are prepended to the question (short-term)
- Retrieved long-term facts are added as a contextual preamble
- After answering, writes user and assistant turns; ingests long facts into long-term memory

## Integration in /architect

- Memory is backend-agnostic: `run_architect_agent` loads turns/summary and
  long-term facts before dispatching to either backend and saves the turn
  after, so builtin and langgraph share the same flags and memory_* audit
  counters; see docs/agents.md
- The langgraph loop receives the loaded context as a system message
  alongside its retrieve_docs tool results

## Configuration

- MEMORY_SHORT_ENABLED: false
- MEMORY_DB_PATH: ./data/memory_short.db
- MEMORY_SHORT_MAX_TURNS: 10
- SHORT_MEMORY_RETENTION_DAYS: 0 (disabled)
- SHORT_MEMORY_MAX_TURNS_PER_SESSION: 0 (disabled)
- MEMORY_LONG_ENABLED: false
- MEMORY_COLLECTION_PREFIX: memory
- MEMORY_LONG_RETENTION_DAYS: 0 (disabled)
- MEMORY_LONG_MAX_FACTS: 0 (disabled)

## Privacy and retention

- Use per-user session identifiers to segregate memory
- Consider data retention policies; short-term DB is a local SQLite file by default

## Export/Import (long-term)

- GET /memory/long/export?user_id=... (analyst/admin): export raw facts for the user
  - Each fact includes: id, text, created_at, metadata, and export-only hints: embedding_present, embedding_dim
- POST /memory/long/import?user_id=... with body {"facts": [{"text": "...", "metadata": {...}}]} to import facts (deduped by text hash)

## Status endpoint (admin only)

- GET /memory/status returns current config, a summary of short/long memory, cumulative pruning counters, and audit metadata

## Delete semantics and idempotency

- DELETE /memory/short clears turns and summary for the given user_id+session_id. Returns cleared=true when the operation succeeds; safe to call repeatedly.
- DELETE /memory/long clears all facts for the given user_id. When MEMORY_LONG_ENABLED=true, the endpoint returns cleared=true even if there was nothing to clear (idempotent semantics).

## Counters and pruning notes

- memory_short_pruned and memory_long_pruned in endpoint audits reflect items pruned during that request only.
- /memory/status aggregates cumulative pruning counters since process start: memory_short_pruned_total, memory_long_pruned_total.
- Retention pruning occurs on reads; max facts/turns enforcement occurs on write or export as noted in code.

## Retention quick start

- SHORT_MEMORY_RETENTION_DAYS=7; SHORT_MEMORY_MAX_TURNS_PER_SESSION=100
- MEMORY_LONG_RETENTION_DAYS=180; MEMORY_LONG_MAX_FACTS=500

## Design

**Owns:** conversational continuity. Two tiers with different lifetimes and shapes:
short-term (verbatim turns per user+session, SQLite) and long-term (distilled facts
per user, in-process semantic store). `app/memory/short_memory.py` and
`app/memory/long_memory.py` own their stores; nothing else writes to them.

**Contract (short):** `load_turns(user_id, session_id) -> [(role, content)]`,
`save_turn(...)`, `load_summary(...)`; pruning (retention days, per-session cap)
happens on read and is reported via `_last_pruned`. **Contract (long):**
`retrieve_facts(user_id, question, top_k)`, `ingest_fact(user_id, text)`.

**Invariants:**
- Keying is always (user_id, session_id) for turns, user_id for facts; an absent
  session_id maps to "default", so callers that want isolation must pass one
  (the eval harnesses generate a fresh session id per example for this reason).
- Memory never fails a request: all memory operations are best-effort with
  exceptions swallowed (set MEMORY_DEBUG=true to surface them).
- Consumers integrate through `run_architect_agent` / the query router, which load
  context before the LLM call and save after; backends never call memory directly
  (this is what keeps memory backend-agnostic across builtin and langgraph).

**Why it exists:** multi-turn coherence for the architect UI and /query without
coupling memory shape to any particular agent implementation.

**Non-goals:** cross-user recall, vector-DB-backed long memory (in-process by
design at this scale), automatic summarization beyond the rolling window.
