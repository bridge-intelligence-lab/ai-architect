# Ports and Adapters Strategy (Library-Agnostic Design)

Purpose
- Keep the API and feature code independent of specific third-party libraries (LangChain, LlamaIndex, Haystack, Semantic Kernel, etc.).
- Enable incremental adoption or replacement of libraries with zero changes to endpoint contracts and minimal changes to feature code.
- Preserve deterministic defaults for tests/CI and provide graceful fallbacks in production when services aren’t configured.

Core patterns
- Ports and Adapters (Hexagonal Architecture): define stable interfaces (ports) owned by us; implement adapters that wrap third-party libraries.
- Strategy: select which adapter to use at runtime via environment/config.
- Pipeline/Decorator: compose optional stages like multi‑query, HyDE, reranking around a base retriever without coupling to a single library’s pipeline.
- Null Object: provide a deterministic “offline” adapter so the system still runs without external dependencies (no network in CI/tests).

Key ports (initial focus first, others later)

1) RAGPort (retrieval + citations)
- Responsibilities
  - retrieve(question, top_k=3, filters=None, options={...}) -> returns citations and flags
  - answer_with_citations(question, top_k=3, options={...}) -> returns answer, citations, flags
  - capabilities() -> declares supported features (e.g., multi_query, hyde, rerank, metadata_filters)
- Options/flags (mapped to env by our façade)
  - RAG_MULTI_QUERY_ENABLED, RAG_MULTI_QUERY_COUNT
  - RAG_HYDE_ENABLED
  - DOCS_PATH, VECTORSTORE_PATH, EMBEDDINGS_PROVIDER
- Providers (adapters)
  - DeterministicAdapter (default; zero network): scans DOCS_PATH for reproducible citations
  - LangChainAdapter (planned/optional): Chroma/FAISS/Pinecone vector stores, MultiQuery, HyDE, rerank
  - LlamaIndexAdapter (planned/optional): QueryEngines, HyDE, rerank, rich metadata
  - HaystackAdapter (planned/optional): Pipelines with BM25+dense, rankers, evaluation
- Selection env
  - Preferred: RAG_BACKEND=deterministic|langchain|llamaindex|haystack
  - Back-compat alias: LC_RAG_BACKEND (if set, it maps to RAG_BACKEND)
- Default behavior
  - DeterministicAdapter in CI/tests for stability; production may opt into LangChain or others.

2) AgentPlannerPort (architect/policy planning)
- Responsibilities
  - plan(question, context_blocks=[], tools=[], schema=None, streaming=False)
  - stream_plan(...) -> yields events for SSE: meta|summary|steps|flags|citations|audit
  - capabilities() -> {tool_use, structured_output, streaming}
- Providers (adapters)
  - BuiltinPlanner (default): current LLMClient + Pydantic JSON output, deterministic stub fallback
  - LangChainPlanner (optional later): LC agents/tools, PydanticOutputParser
  - SemanticKernelPlanner (optional later): SK planners and skills (Python/C#/Java)
  - CrewAIPlanner (optional later): multi-agent orchestration
- Selection env
  - AGENT_BACKEND=builtin|langchain|semantic_kernel|crewai (default: builtin)

3) ToolPort (tools callable by planners)
- Responsibilities
  - list_tools() -> [ToolSpec(name, input_schema, output_schema, rbac, costs)]
  - call_tool(name, args, context) -> result
- Tools to expose (wrap our services)
  - search, fetch, pii_detect, rag_retrieve, memory_read/write, policy_retrieve, risk_score
- Rationale
  - Keep tools consistent no matter which planner backend is used.

4) EmbeddingsPort
- embed(texts) -> vectors; reports provider/model/dims
- Providers: stub (deterministic), local (sentence-transformers), OpenAI, others later
- Used by RAG adapters to remain provider-agnostic

5) VectorStorePort
- upsert(documents), query(vectors|texts, top_k, filters)
- Providers: Chroma, FAISS (local), Pinecone, PgVector, Weaviate, etc.

6) TracePort (observability)
- start_span(name, attrs) / end_span / annotate
- Providers: no-op (default), LangSmith, OpenTelemetry

7) MemoryPort (optional wrapper)
- Thin wrapper around existing short/long memory so agents can call memory uniformly via ToolPort.

Env/config conventions
- RAG_BACKEND: deterministic|langchain|llamaindex|haystack (preferred)
- LC_RAG_BACKEND: legacy alias; mapped into RAG_BACKEND if present
- AGENT_BACKEND: builtin|langchain|semantic_kernel|crewai (default: builtin)
- EMBEDDINGS_PROVIDER: stub|local|openai (default: stub/local for determinism)
- VECTORSTORE_BACKEND (future): chroma|faiss|pinecone|pgvector|weaviate
- TRACE_BACKEND: none|langsmith|otel
- Flags used by RAG options: RAG_MULTI_QUERY_ENABLED, RAG_MULTI_QUERY_COUNT, RAG_HYDE_ENABLED

Rollout plan (incremental)
- Phase 1 (now): Document ports; keep current behavior. Prefer RAG_BACKEND flag (alias supported). Deterministic remains default.
- Phase 2: Introduce RAGPort and DeterministicAdapter in code; keep existing function signatures (e.g., answer_with_citations) calling through the port, so tests remain unchanged.
- Phase 3: Implement LangChainAdapter (Chroma by default), fallback to Deterministic when unconfigured.
- Phase 4: Introduce AgentPlannerPort with BuiltinPlanner; wire Architect agent to resolve planner via AGENT_BACKEND.
- Phase 5: Add optional adapters (LlamaIndex/Haystack planners/retrievers; Semantic Kernel planner; CrewAI), all with graceful fallbacks.

Backward compatibility and fallbacks
- Endpoints keep the same request/response contracts.
- If selected backend is missing/unconfigured, we fall back to Deterministic (RAG) or Builtin (Planner) and record the fallback in audit metadata.
- Tests/CI always pass without network/API keys.

Mapping to current code
- RAG today: app/services/langchain_rag.py provides answer_with_citations with deterministic behavior and feature flags (multi-query, HyDE). This will become a façade over RAGPort.
- Query and Architect routes already accept grounded mode and emit citations; they will keep working after we swap the underlying adapter.
- LLM calls: app/services/llm_client.py already provides a provider-agnostic client with stub fallback; this aligns with the Planner port.
- Memory: existing short/long memory modules will be wrapped via ToolPort for agent tool calls.

Observability
- Keep structured logging and metrics; add TracePort to integrate LangSmith or OpenTelemetry as optional backends without coupling the rest of the system.

Summary
- We standardize on ports (RAG, Planner, Tools, Embeddings, VectorStore, Trace) with Strategy-based selection and Null-Object defaults.
- This lets us implement features once and switch libraries later by replacing adapters, not rewriting features.
