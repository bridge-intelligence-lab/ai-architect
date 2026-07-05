---
title: Configuration
status: current
module: ops
last_reviewed: 2026-07-04
source:
  - .env.example
---

# Configuration

Environment variables (selected). Defaults shown are the code defaults when the
variable is unset; `.env.example` documents a working local setup.

## Core

- APP_ENV: runtime profile (default: local)
- LOG_LEVEL: logging level (default: INFO)
- REQUEST_ID_HEADER: request ID header name (default: X-Request-ID)
- METRICS_TOKEN: if set, /metrics requires header X-Metrics-Token with this value
- DB_URL: database URL (default: sqlite:///./audit.db)

## Backends (the headline switches)

- AGENT_BACKEND: builtin|langgraph — architect implementation (default: builtin;
  langgraph won the measured comparison, see docs/eval_results/)
- RAG_BACKEND: keyword_scan|vector — retrieval path (default: keyword_scan;
  vector uses the Chroma store fed by scripts/ingest_docs.py)
- PII_BACKEND: regex|presidio — PII detector engine (default: regex)
- ROUTER_ENABLED: enable the rules-based Router Agent for intent selection (default: false)
- ROUTER_BACKEND, ROUTER_RULES_JSON, ROUTER_RULES_PATH: router implementation and rules override

## LLM

- LLM_PROVIDER: stub|openai|... (default: stub, deterministic offline; real providers route through LiteLLM)
- LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS (default: 512)
- LLM_ENABLE_QUERY, LLM_ENABLE_ARCHITECT: opt LLM synthesis into /query and /architect (default: false)
- PROJECT_GUIDE_ENABLED: gates the /architect endpoint (default: false)
- OPENAI_API_KEY and other provider keys: read by LiteLLM at call time

## Retrieval

- DOCS_PATH: corpus root. Careful: the keyword-scan query path defaults to ./examples
  while scripts/ingest_docs.py defaults to ./docs — set it explicitly
- VECTORSTORE_PATH: Chroma persistence path; RAG_COLLECTION: collection name
- RAG_EXCLUDE_FILES: comma-separated basenames never used as grounding context
  (defaults include the eval/prompt docs; applied at keyword scan, vector query, and ingestion)
- RAG_EXCLUDE_DIRS: directory names excluded the same way (default: worklog)
- RAG_MULTI_QUERY_ENABLED, RAG_MULTI_QUERY_COUNT, RAG_HYDE_ENABLED: query expansion
  (keyword-scan path only; no-ops under RAG_BACKEND=vector)
- EMBEDDINGS_PROVIDER: openai|local|hash|stub (recommended: openai; see docs/rag.md for why)
- LOCAL_EMBEDDING_MODEL (default: all-MiniLM-L6-v2), OPENAI_EMBEDDING_MODEL (default: text-embedding-3-small)

## PII / Risk

- PII_TYPES: comma-separated detectors (default: email,phone,ssn,credit_card,ipv4); PII_LOCALES
- PII_PRESIDIO_THRESHOLD (default: 0.5), PII_SPACY_MODEL (default: en_core_web_sm): presidio backend knobs
- RISK_ML_ENABLED: ML-style risk scorer instead of heuristics (default: false); RISK_THRESHOLD (default: 0.6)

## Memory

- MEMORY_SHORT_ENABLED: enable short-term memory (default: false)
- MEMORY_DB_PATH: SQLite path for short memory (default: ./data/memory_short.db)
- MEMORY_SHORT_MAX_TURNS: max turns before summary (default: 10)
- SHORT_MEMORY_RETENTION_DAYS, SHORT_MEMORY_MAX_TURNS_PER_SESSION (default: 0=disabled)
- MEMORY_LONG_ENABLED (default: false), MEMORY_COLLECTION_PREFIX (default: memory)
- MEMORY_LONG_RETENTION_DAYS, MEMORY_LONG_MAX_FACTS (default: 0=disabled)
- Note: memory integrates with /query and /architect; for /architect it is
  backend-agnostic (both builtin and langgraph read/write it)

## Research agent safety

- AGENT_LIVE_MODE: allow live HTTP fetch in /research (default: false)
- AGENT_URL_ALLOWLIST, DENYLIST: fetch allowlist and risk-check denylist

## ML / MLflow

- MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME (default: ai-architect)
- MLFLOW_MODEL_URI, MLFLOW_MODEL_ARTIFACT_PATH, MLFLOW_FEATURE_ORDER_ARTIFACT, MLFLOW_MODEL_CACHE_TTL
- ML_BASELINE_DATA, ML_INPUT_DATA: paths for drift script defaults

## Tracing / Eval

- LANGCHAIN_TRACING_V2 + LANGCHAIN_API_KEY: enable LangSmith tracing (both required)
- LANGCHAIN_PROJECT: LangSmith project runs land in
- EVAL_JUDGE_MODEL: LLM-judge model for the eval pipeline (default: gpt-4.1-mini)

See .env.example for a working local setup.

Install notes:
- CPU-only Docker builds install sentence-transformers using the PyTorch CPU wheel index so torch resolves to CPU wheels.
- For GPU builds, adjust the Dockerfile to use a CUDA-specific index and compatible torch versions.
