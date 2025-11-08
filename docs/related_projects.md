# Related Open-Source Projects (Complementary Landscape)

Purpose
- Provide a curated view of adjacent OSS so users understand how this project fits and complements the ecosystem.
- Keep the root README vendor-neutral; this page lives under docs/.

Summary
- Many projects offer strong building blocks (frameworks, agents, tracing, model routing). This project aims to be a cohesive, library-agnostic service with deterministic defaults, RBAC/PII, memory, audit/metrics, and SSE streaming — all fronted by stable ports and adapters.

Frameworks (RAG, chains, agents)
- LangChain — https://github.com/langchain-ai/langchain
  - Large ecosystem of chains/agents, tools, and vector DB connectors; supports MultiQuery, HyDE, parent-child docs, and LCEL. Excellent for composing retrieval and agents; LC-first abstractions.
- LlamaIndex — https://github.com/run-llama/llama_index
  - Strong indexing/query engines (VectorStoreIndex, Summary/Tree/KnowledgeGraph), robust Node/metadata model, SubQuestion/Router engines, HyDE, and rerankers. Great for complex retrieval orchestration.
- Haystack — https://github.com/deepset-ai/haystack
  - Production-oriented QA pipelines, DocumentStores (Elasticsearch/Weaviate/FAISS/Pinecone), BM25 + dense retrievers, rankers, and evaluation tooling.
- Semantic Kernel — https://github.com/microsoft/semantic-kernel
  - Multi-language (C#/Python/Java) skills/plugins, planners, and tool execution; good enterprise fit for agent tool calls.

Agent orchestration
- CrewAI — https://github.com/joaomdmoura/crewAI
  - Multi-agent roles, collaborative workflows; useful for advanced planning/delegation.
- AutoGen — https://github.com/microsoft/autogen
  - Agent-to-agent collaboration patterns and tools; research-driven.
- LangGraph — https://github.com/langchain-ai/langgraph
  - State-graph approach to LLM apps; complements or replaces classical agent loops.

Model routing and providers
- LiteLLM — https://github.com/BerriAI/litellm
  - Unifies LLM provider APIs, retries, cost tracking; a strong candidate to back an LLMPort.

Tracing, evaluation, and observability
- Langfuse — https://github.com/langfuse/langfuse
  - Tracing, analytics, data management for LLM apps; good for a TracePort adapter.
- OpenTelemetry — https://opentelemetry.io/
  - Vendor-neutral tracing/metrics/logs; use OTLP exporters to integrate with existing infra.
- Arize Phoenix — https://github.com/Arize-ai/phoenix
  - Observability for LLM/RAG systems; experiment tracking and exploration.
- TruLens — https://github.com/truera/trulens
  - Evaluation framework with feedback functions and RAG measurements.

Guardrails / Policy
- NeMo Guardrails — https://github.com/NVIDIA/NeMo-Guardrails
- GuardrailsAI — https://github.com/shreyar/guardrails
  - Guardrail grammars, policy checks, and safety flows; can be integrated as ToolPort steps or Planner pre/post-processors.

RAG servers and low-code builders
- LangServe — https://github.com/langchain-ai/langserve
  - Expose LangChain chains as REST; LC-first, not multi-lib.
- Haystack REST API — examples under the Haystack repo
  - Pipeline-as-API for Haystack; framework-specific.
- Flowise — https://github.com/FlowiseAI/Flowise
- LangFlow — https://github.com/logspace-ai/langflow
  - Visual builders for chain/agent prototyping; can call or generate code for our service.

Vector stores and embeddings (building blocks)
- Vector DBs: Chroma, FAISS, Pinecone, Weaviate, Qdrant, PgVector
- Embeddings: sentence-transformers (local), OpenAI, others
  - These sit behind a VectorStorePort and EmbeddingsPort in our design for provider-agnostic wiring.

Document loaders and ingestion
- Unstructured — https://github.com/Unstructured-IO/unstructured
  - Document loading/parsing pipelines; helpful for ingestion scripts regardless of framework.

How this project complements the ecosystem
- Library-agnostic ports and adapters: RAGPort, AgentPlannerPort, ToolPort, Embeddings/VectorStore/Trace ports; Strategy-based selection at runtime.
- Deterministic-by-default operation: offline stubs and reproducible tests; graceful fallbacks in production.
- Cohesive service layer: FastAPI with RBAC, PII detection/remediation, short/long memory, audit, metrics, and SSE streaming.
- Integrates rather than replaces: you can plug in LangChain, LlamaIndex, Haystack, Semantic Kernel, etc., without changing endpoint contracts.

Next steps
- See docs/ports_and_adapters.md for the architecture and rollout plan.
