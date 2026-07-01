# ADR 0004: Build-vs-buy policy for AI-Architect components

Date: 2026-07-01

Status: Accepted

Context
- Much of this repo was hand-rolled in late 2025 while learning the LLM/agent
  stack, rather than adopting a framework. Reviewing it in 2026, the question is
  not "hand-rolled vs library" in the abstract, but per component: does the
  custom implementation cost us anything real, or is it the better call?
- A custom implementation is read two ways by a reviewer: "reinvented the wheel"
  or "understood the primitives and made a deliberate call." The difference is a
  documented decision plus the code actually being good. This ADR is that
  documentation. It builds on the ports in [ADR-0001](0001-ports-and-adapters.md):
  most changes fill a real adapter behind an existing port.

Decision
Classify each component into keep (hand-rolled, on purpose), adopt (a library
earns its place), or decide (depends on ambition). Rationale is the axis on which
the current code is measured, not fashion.

- **Keep (hand-rolled is right; document, do not replace):**
  - `router.py` — keyword/rule intent routing for a bounded intent set:
    deterministic, zero-latency, zero-token, testable. An LLM router would add
    cost and nondeterminism for no gain. Keep; optionally add an `llm` backend
    behind the existing `ROUTER_BACKEND` switch.
  - `app/utils/*` audit, RBAC, cost, retention — app-specific, no dominant
    library; these are the project's differentiators. Owning them is correct.
  - `rag_retriever.py` embeddings shim (stub / local / OpenAI) — a small, clean
    abstraction behind `EmbeddingsPort`. Keep.
  - prompt registry (`render_prompt` + `prompts/*.yaml`) — simple, versioned.
    A prompt-management library adds little at this scope.
  - `mlflow_client.py` — already a library (MLflow). Correct.

- **Adopt (custom version is worse on a real axis):**
  - LLM client (`llm_client.py`) → **LiteLLM** (hybrid: keep the `stub`
    provider). The hand-rolled client hardcodes `cost_usd: 0.0` in every branch,
    which guts the project's own FinOps claim. LiteLLM provides real per-model
    cost, fallbacks, and 100+ providers. (PR E.)
  - Output parsing (`prompt_runner.parse_json_safe`) → **native structured
    outputs / tool-use**. ~150 lines of defensive JSON scraping is exactly what
    provider-native structured output solves; it also removes the dead
    `langchain.schema` import that pins us to `langchain==0.1.11`. (PR D.)
  - Doc RAG (`langchain_rag.py`) → **real vector retrieval**. Despite the name it
    imports no langchain and returns a hardcoded stub answer; the flagship
    feature is hollow. Chroma + sentence-transformers are already dependencies.
    (PRs B, C.)

- **Decide by ambition:**
  - The "architect agent" (`architect_agent.py`) is a linear chain, not an agent
    (no tool loop). Decision: **build a real LangGraph agent** behind
    `AGENT_BACKEND` rather than rename it a chain, delivering the capability the
    roadmap previously claimed. (PR F.)

Consequences
- Modernizing here *reduces* framework coupling: PR D lets us drop the
  heavyweight `langchain` package down to `langchain-core`.
- The deterministic Null-Object defaults from ADR-0001 remain the CI/offline
  path; adopted libraries sit behind ports and env flags, not in the hot path by
  default.
- Claims and code converge: PR A removes the overstated roadmap entries; PRs
  C/E/F make the corresponding features real, then the roadmap is updated to
  "shipped" truthfully.

Alternatives considered
- Blanket "adopt frameworks to shrink the code": rejected. It is what pinned us
  to a stale `langchain` in the first place, and would replace defensible custom
  code (router, audit) with coupling for no benefit.
- Blanket "keep everything hand-rolled": rejected. It leaves the FinOps claim
  false (cost=0), the RAG hollow, and the parser fragile.

Implementation notes
- Sequenced in [docs/MODERNIZATION_PLAN.md](../MODERNIZATION_PLAN.md) as PRs A–I.
- Order: honesty (A) → RAG rename/real (B, C) → structured outputs (D) → LiteLLM
  (E) → LangGraph agent (F) → optional MCP (G), Presidio (H), CI gate (I).

References
- docs/MODERNIZATION_PLAN.md
- docs/adr/0001-ports-and-adapters.md
- docs/rag.md, docs/agents.md, docs/observability.md
