---
title: Architecture index
status: current
module: architecture
last_reviewed: 2026-07-05
source:
  - app/main.py
---

# Architecture index

The system map: how a request flows through the subsystems, and where each
subsystem's deep description lives. Each linked doc ends with a **Design** section
covering what the module owns, its contract, invariants, and non-goals.

## Life of an /architect request

1. **Gateway** (`app/main.py`): middleware attaches a request id and metrics timers;
   RBAC parses `X-User-Role`.
2. **Wrapper** (`run_architect_agent`, [agents.md](agents.md)): loads short-term
   turns and long-term facts ([memory.md](memory.md)), then dispatches by
   `AGENT_BACKEND`.
3. **Backend**: builtin (deterministic planner: retrieval, one structured LLM call)
   or langgraph (tool loop that may call `retrieve_docs` up to 3 times). Both
   ground through the retrieval facade ([rag.md](rag.md)); both call the LLM through
   LLMClient (LiteLLM routing, real cost tracking).
4. **Wrapper again**: applies the feature-CTA heuristic, saves the turn to memory,
   merges memory counters into the audit.
5. **Delivery**: `/architect` returns JSON; `/architect/stream` emits SSE
   (status, then meta/summary/steps/flags/citations, optional feature, final audit;
   error on failure). Contract in [agents.md](agents.md).
6. **Governance**: an audit row is written best-effort ([audit.md](audit.md));
   metrics land in Prometheus ([observability_metrics.md](observability_metrics.md));
   a LangSmith run tree is posted when tracing is enabled
   ([observability.md](observability.md)).

## Life of a /query request

The router selects the intent ([router.md](router.md)): qa goes through the same
retrieval facade (grounded) or optional LLM synthesis; pii/risk/policy intents
dispatch to their services ([pii.md](pii.md); full endpoint list in
[capabilities_current.md](capabilities_current.md)). Memory and audit behave as
above.

## Subsystem map

| Subsystem | Doc (with Design section) | Code |
|---|---|---|
| Architect agent (both backends) | [agents.md](agents.md) | app/services/architect_agent.py, app/services/langgraph_architect.py |
| Retrieval / RAG | [rag.md](rag.md) | app/services/doc_retriever.py, app/services/vector_retriever.py |
| Memory (short + long) | [memory.md](memory.md) | app/memory/ |
| Router (intents) | [router.md](router.md) | app/services/router.py |
| Audit | [audit.md](audit.md) | app/utils/audit.py, db/ |
| Metrics / tracing | [observability.md](observability.md), [observability_metrics.md](observability_metrics.md) | app/utils/metrics.py |
| Evaluation | [langsmith_test_plan.md](langsmith_test_plan.md), eval_results/ | scripts/ |

## Cross-cutting rules

- Cross-cutting agent behavior (memory, feature CTA) lives in the wrapper, never in
  a backend ([agents.md](agents.md) Design).
- docs/ is the RAG corpus; docs/worklog/ is excluded ([rag.md](rag.md) Design).
- Offline determinism is the CI default: stub LLM + keyword_scan + builtin backend.
- Every endpoint audits best-effort; auditing never fails a request.

## Use case mapping checklist

- Define intent (QA vs PII vs Risk vs Research)
- Choose grounded=true when you need citations
- Identify env flags to enable features ([config.md](config.md))
- Outline endpoints and services to modify ([components.md](components.md))
