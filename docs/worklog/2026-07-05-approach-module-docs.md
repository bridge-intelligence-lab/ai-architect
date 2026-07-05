# Approach: module docs + docstrings (backlog item 5)

Status: APPROVED 2026-07-05
Relates to: 2026-07-04-docs-knowledge-backlog.md item 5.

## Goal

Give the runtime agent (via the corpus) and maintainers a deep, per-subsystem
understanding: what each module owns, its contracts, and why it exists. Docstrings
serve code readers; module docs serve the agent.

## Design decision (flagging explicitly)

NOT creating a parallel docs/modules/ tree. The subsystem docs already exist (rag.md,
agents.md, memory.md, router.md, audit.md, observability.md) and are usage/config
focused. A parallel tree would duplicate content in the corpus, and duplication is
retrieval noise. Instead each subsystem doc gains a **Design** section: what the module
owns, its public contract (functions/inputs/outputs), key invariants, why it exists,
and what it deliberately does not do. architecture_index.md becomes the map that ties
them together.

## Plan

1. Design sections (judgment work, main model, one commit per subsystem):
   - rag.md — retrieval facade contract, backend selection, exclusion invariants,
     the never-deletes ingest property, fallback chain
   - agents.md — run_architect_agent as the backend-agnostic wrapper (memory +
     CTA invariants), builtin vs langgraph contracts, fallback semantics
   - memory.md — two-tier design, session keying, pruning semantics, audit counters
   - router.md — intent contract, rules vs builtin resolution order
   - audit.md + observability.md — audit row contract, what is guaranteed best-effort
   - architecture_index.md — request lifecycle walk-through linking the above
2. Docstrings (mechanical batches, haiku agents, explicit model override):
   - Public surfaces first: app/routers/*, app/services/*, app/memory/*, both agent
     backends. Module-level docstring + public functions. Skip trivial helpers.
   - Style: concise, states contract and gotchas, no narration of obvious code.
3. CLAUDE.md pointers updated to the Design sections.

## Verification

- Full test suite (docstrings must not change behavior; pure additions).
- Store rebuild + eval run, diff vs docs-overhaul-headings-0d660fad. Design sections
  add corpus content, so this is a measurable corpus change.
- Docstring batches spot-checked for accuracy against the code they describe
  (wrong docstrings are worse than none).

## Out of scope

- Intent-flexible responses (item 6), Makefile (item 7).
- Docstrings for tests, scripts/, ml/ (lower value; can follow later).
