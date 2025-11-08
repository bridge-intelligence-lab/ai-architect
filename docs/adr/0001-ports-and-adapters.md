# ADR 0001: Ports-and-Adapters for AI-Architect

Date: 2025-10-11

Status: Accepted

Context
- We integrate with rapidly evolving LLM/RAG and agent libraries (LangChain, LlamaIndex, Haystack, Semantic Kernel, CrewAI, etc.).
- We must keep endpoint contracts stable, preserve deterministic tests/CI, and allow gradual adoption or replacement of libraries.

Decision
- Adopt Ports-and-Adapters (Hexagonal Architecture) as our primary architectural pattern, combined with:
  - Strategy for runtime adapter selection via env/config.
  - Pipeline/Decorator to compose optional retrieval stages (multi-query, HyDE, rerank) orthogonally.
  - Null Object defaults (deterministic implementations) to ensure offline operation in tests/CI.
- Define initial ports: RAGPort, AgentPlannerPort, ToolPort, EmbeddingsPort, VectorStorePort, TracePort; optional MemoryPort wrapper.
- Prefer env flags: RAG_BACKEND and AGENT_BACKEND (with LC_RAG_BACKEND as a legacy alias). Preserve deterministic defaults.

Consequences
- Default behavior remains unchanged and deterministic; production can opt into richer backends.
- Third-party library swaps do not change endpoint code; we replace adapters.
- Slight increase in internal abstraction, offset by better evolvability and testability.

Alternatives considered
- Direct integration with a single library (e.g., LangChain): faster initially, but increases coupling and migration cost.
- Only Adapter pattern: doesn’t address composition of optional stages; Pipeline/Decorator is needed.
- Microservice split for each capability: heavier operational cost; not necessary at current scope.

Implementation notes
- Start by documenting (this ADR and docs/ports_and_adapters.md).
- Next phases: introduce RAGPort with DeterministicAdapter (no behavior change), then LangChain/LlamaIndex adapters, then AgentPlannerPort with BuiltinPlanner.

References
- docs/ports_and_adapters.md
- docs/rag.md
- docs/agents.md
