---
title: Agents
status: current
module: agents
last_reviewed: 2026-07-04
source:
  - app/services/architect_agent.py
  - app/services/langgraph_architect.py
  - app/routers/architect.py
---

# Agents

## Architect backends (AGENT_BACKEND)

The `/architect` endpoints run one of two backends, selected by
`AGENT_BACKEND`:

- **`builtin` (default).** Deterministic linear pipeline in
  `app/services/architect_agent.py`: memory read → retrieval → one LLM call
  with `PydanticOutputParser` format instructions → validated
  `ArchitectPlan` → memory write. Fully offline with the stub LLM; this is
  what tests and CI exercise.
- **`langgraph`.** Real tool-loop agent in
  `app/services/langgraph_architect.py`: a LangGraph `StateGraph` where the
  LLM decides each turn whether to call the `retrieve_docs` tool (backed by
  `doc_retriever`, so `RAG_BACKEND=vector` applies) or finalize the plan.
  Tool observations feed back into the next turn; the loop is capped at 3
  tool calls. When the budget is exhausted the agent receives an explicit
  finalize-now instruction, and a plan that still comes back empty raises so
  the builtin fallback fires instead of streaming an empty plan. Tokens and
  cost accumulate across turns into the audit, which also reports
  `agent_backend` and `agent_tool_calls`. Any failure falls back to the
  builtin planner.

Memory and the feature-request heuristic are backend-agnostic: they run in
`run_architect_agent` around whichever backend is selected, so both backends
read/write session memory (the langgraph loop receives loaded context as a
system message) and both can emit the feature CTA. See docs/memory.md.

In a measured comparison on the golden eval dataset, `langgraph` beat
`builtin` on groundedness, correctness, completeness AND latency, so the
default is the offline-safe choice, not necessarily the recommended one.
See `docs/eval_results/2026-07-04-grid-backend-tokens.md`.

## Architect agent and community loop

- The Architect agent can propose features when it detects gaps between a user goal and current capabilities (e.g., a new endpoint or a router rule).
- Users can copy the proposal (summary, steps, flags) into a GitHub issue; see docs/llm_agent_streaming_prompts.md for a ready-to-use prompt set.
- This closes the loop between learning, brainstorming, and contribution, keeping the repo a living reference architecture.

## Research Agent

- Endpoint: POST /research (analyst/admin; per-step RBAC applies)
- Steps:
  1) search(topic) -> [{title, url}]
  2) fetch(urls) -> [{url, text}]
  3) summarize(docs) -> findings: [{title, summary, url}]
  4) risk_check(topic, findings) -> flagged: bool (uses DENYLIST)
- Config:
  - AGENT_LIVE_MODE (default: false) — when true, fetch performs real HTTP GETs (limited)
  - AGENT_URL_ALLOWLIST (comma-separated prefixes) — restricts live fetch to allowed domains/prefixes
  - DENYLIST (comma-separated terms) — flags risky research content in risk_check
- RBAC:
  - fetch/search/summarize: analyst+
  - risk_check: guest+
- Audit: steps include {name, inputs, outputs.preview, latency_ms, hash, timestamp}

## Policy Navigator Agent

- Endpoint: POST /policy_navigator (analyst/admin)
- Behavior:
  1) Decompose policy question into sub-questions (max POLICY_NAV_MAX_SUBQS, default 3)
  2) Retrieve citations per sub-question using existing retriever
  3) Synthesize a concise recommendation referencing evidence
- Config:
  - POLICY_NAV_ENABLED (default: true)
  - POLICY_NAV_MAX_SUBQS (default: 3)
- Audit: includes step entries for decompose, retrieve, synthesize with inputs/outputs preview and latency

## Architect Agent

- Endpoints:
  - POST /architect — returns an ArchitectResponse with answer, citations (when grounded), suggested_steps, suggested_env_flags, and audit
  - GET /architect/stream — Server-Sent Events (SSE) stream for progressive updates
  - GET /architect/ui — HTML chat UI
- Flags:
  - PROJECT_GUIDE_ENABLED (default: false) — enables /architect API; UI shows a badge when disabled
  - LLM_ENABLE_ARCHITECT (default: false) — when true, uses LLM-backed agent for plan generation
  - DOCS_PATH — path to docs corpus for grounding; RAG flags apply
  - RAG_MULTI_QUERY_ENABLED, RAG_MULTI_QUERY_COUNT, RAG_HYDE_ENABLED — retrieval behavior
  - MEMORY_SHORT_ENABLED (default: false) — enables short-term conversation memory
  - MEMORY_LONG_ENABLED (default: false) — enables long-term semantic fact memory
- Memory Integration:
  - When MEMORY_SHORT_ENABLED=true, the agent loads recent conversation turns and prepends them to the context
  - When MEMORY_LONG_ENABLED=true, the agent retrieves relevant facts from past sessions and injects them as background context
  - After generating a plan, the agent saves the conversation turn and ingests key insights (summary, steps, feature requests) as long-term facts
  - Memory audit fields are included in the response: memory_short_reads, memory_short_writes, memory_long_reads, memory_long_writes, memory_short_pruned, memory_long_pruned, summary_updated
  - See docs/memory.md for retention and configuration details
- SSE event contract (/architect/stream):
  - event: status
    data: "planning" — emitted immediately on connect, before the agent runs
  - event: error
    data: string — server-side failure message; stream ends after this
  - event: meta
    data: { "provider": string|null, "model": string|null, "grounded_used": bool|null }
  - event: summary
    data: string — a human-readable summary; may occur once
  - event: steps
    data: [string] — suggested steps (optional)
  - event: flags
    data: [string] — suggested env flags (optional)
  - event: citations
    data: [ { source: string, page?: number|null, snippet?: string|null } ] (optional)
  - event: feature
    data: { title?: string, summary?: string, steps?: [string], flags?: [string], citations?: [...] } (optional CTA)
  - event: audit
    data: { ... } — final audit metadata (tokens/cost if LLM used, rag flags, grounded_used, etc.)

## PII Remediation Agent

- Endpoint: POST /pii_remediation (analyst/admin)
- Behavior:
  1) Detect PII entities in the input text
  2) Retrieve relevant remediation guidance (when grounded=true)
  3) Synthesize actionable redactions and optional code snippets
- Config:
  - PII_REMEDIATION_ENABLED (default: true)
  - PII_REMEDIATION_INCLUDE_SNIPPETS (default: true)
- Output: remediation items per type, optional citations and snippets

---

## See also

- ports_and_adapters.md: interface-first architecture and planner/RAG backends
- related_projects.md: curated ecosystem overview and how this project complements it
