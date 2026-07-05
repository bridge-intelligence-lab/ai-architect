---
title: ADR 0007: LangGraph tool-loop architect behind AGENT_BACKEND
status: current
module: architecture
last_reviewed: 2026-07-05
decision_date: 2026-07-04
adr_status: Accepted
---

# ADR 0007: LangGraph tool-loop architect behind AGENT_BACKEND

## Context

- The "architect agent" was a deterministic linear chain (memory →
  retrieval → single LLM call → parse), not an agent: the model never
  decides anything about control flow. ADR-0004 posed the choice for row F:
  rename honestly, or build a real agent. The decision (2026-07-01) was to
  build the real agent while keeping the deterministic path.
- LangGraph is the production standard for agent loops in 2026 and we
  already carry `langchain-core`; a hand-rolled while-loop would re-implement
  state routing, checkpointing hooks, and conditional edges for no benefit
  (build-vs-buy: the library wins on its own claim here).

## Decision

- Add `app/services/langgraph_architect.py`: a `StateGraph` with an `agent`
  node (LLM decides: call a tool or finalize) and a `tools` node
  (`retrieve_docs` via `doc_retriever`, so the vector backend applies when
  enabled), connected by conditional edges; capped at 3 tool calls.
- The LLM speaks a strict JSON action protocol; non-protocol replies become
  the final summary instead of failing the run (important for weak/stub
  models).
- `AGENT_BACKEND=langgraph` opts in; `builtin` remains the default. The
  dispatcher lives at the top of `run_architect_agent`, so all call sites
  (`/architect`, `/architect/stream`, `/think`) get the flag for free, and
  any LangGraph failure falls back to the builtin planner.
- Audit gains `agent_backend` (which path actually ran) and
  `agent_tool_calls`; tokens/cost accumulate across loop turns via the
  LiteLLM client (ADR 0006 seam).

## Consequences

- The repo's "agent" claim is now real: model-driven control flow with tool
  feedback, observable in the audit trail.
- Memory read/write integration remains builtin-only in this iteration;
  wiring it into the graph is a natural follow-up node.
- Tests script the LLM turns, so the loop, the cap, grounding, fallback,
  and cost accumulation are all covered offline and deterministically.
- New dependency: `langgraph>=1.0.0` (verified against 1.2.7 with
  langchain-core 1.4.8).
