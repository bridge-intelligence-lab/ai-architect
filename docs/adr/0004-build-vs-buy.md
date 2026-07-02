# ADR 0004: Build-vs-buy policy for AI-Architect components

Date: 2026-07-01

Status: Accepted

Context
- Much of this repo was hand-rolled in late 2025 while learning the LLM/agent
  stack, rather than adopting a framework. Reviewing it in 2026, the question
  is not "hand-rolled vs library" in the abstract, but per component: is the
  custom implementation the better call, or does a library win on a real axis?
- A custom implementation should be a documented, deliberate decision. This
  ADR is that documentation. It builds on the ports in
  [ADR-0001](0001-ports-and-adapters.md): most changes fill a real adapter
  behind an existing port.

Scope
- ai-architect has a single purpose: a reference implementation for running
  LLM and agent services with production controls (RBAC, audit, FinOps,
  retrieval, MLOps) on a FastAPI + ports-and-adapters core. Domain-specific
  scenarios and standalone design explorations live outside this repo;
  multi-agent capability enters as working code via the planned LangGraph and
  MCP PRs. The Mandala design documents were removed from HEAD under this
  policy (they remain in git history).

Decision
Classify each component into keep (hand-rolled, on purpose), adopt (a library
earns its place), or decide (depends on ambition). Rationale is the axis on
which the current code is measured, not fashion.

- **Keep (hand-rolled is right; document, do not replace):**
  - `router.py` — keyword/rule intent routing for a bounded intent set:
    deterministic, zero-latency, zero-token, testable. An LLM router would add
    cost and nondeterminism for no gain. Keep; optionally add an `llm` backend
    behind the existing `ROUTER_BACKEND` switch.
  - `app/utils/*` audit, RBAC, cost, retention — app-specific, no dominant
    library; these are the project's differentiators. Owning them is correct.
  - `rag_retriever.py` embeddings shim (stub / local / OpenAI) — a small,
    clean abstraction behind `EmbeddingsPort`. Keep.
  - prompt registry (`render_prompt` + `prompts/*.yaml`) — simple, versioned.
    A prompt-management library adds little at this scope.
  - `mlflow_client.py` — already a library (MLflow). Correct.

- **Adopt (a library wins on a real axis):**
  - LLM client (`llm_client.py`) → **LiteLLM** (hybrid: keep the `stub`
    provider). LiteLLM provides real per-model cost, fallbacks, and 100+
    providers, which lets the FinOps metrics report actual spend instead of a
    placeholder value. (PR E.)
  - Output parsing (`prompt_runner.parse_json_safe`) → **native structured
    outputs / tool-use**. ~150 lines of defensive JSON scraping is exactly
    what provider-native structured output solves; it also lets us drop the
    stale `langchain==0.1.11` pin down to `langchain-core`. (PR D.)
  - Doc retrieval (`langchain_rag.py`) → **real vector retrieval**. The
    current implementation is a deterministic keyword baseline; Chroma +
    sentence-transformers are already dependencies, so the vector path is the
    natural next step. The module is renamed to match what it does. (PRs B, C.)

- **Decide by ambition:**
  - The architect (`architect_agent.py`) currently runs a deterministic
    planner (no tool loop). Decision: **build a real LangGraph tool-loop
    agent** behind `AGENT_BACKEND`, keeping the deterministic planner as the
    default/offline path. (PR F.)

Consequences
- Modernizing here *reduces* framework coupling: PR D lets us drop the
  heavyweight `langchain` package down to `langchain-core`.
- The deterministic Null-Object defaults from ADR-0001 remain the CI/offline
  path; adopted libraries sit behind ports and env flags, not in the hot path
  by default.
- The roadmap separates shipped from planned per component, and each up-level
  PR moves its component from planned to shipped.

Alternatives considered
- Blanket "adopt frameworks to shrink the code": rejected. It is what pinned
  us to a stale `langchain` in the first place, and would replace defensible
  custom code (router, audit) with coupling for no benefit.
- Blanket "keep everything hand-rolled": rejected. It leaves FinOps cost
  reporting on a placeholder, retrieval on the keyword baseline, and the
  parser fragile.

Implementation notes
- Sequenced in [docs/MODERNIZATION_PLAN.md](../MODERNIZATION_PLAN.md) as PRs
  0 and A–I.
- Order: CI health (0) → scope/roadmap docs (A) → retrieval rename/vector
  (B, C) → structured outputs (D) → LiteLLM (E) → LangGraph agent (F) →
  optional MCP (G), Presidio (H), coverage gate (I).

References
- docs/MODERNIZATION_PLAN.md
- docs/adr/0001-ports-and-adapters.md
- docs/rag.md, docs/agents.md, docs/observability.md
