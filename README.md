# 🧠 AI Architect
> **Architect-first open-source platform for designing safe, observable, and cost-aware AI systems.**  
> Primary interface: **/architect** — a meta-agent that orchestrates RAG, agents, and ML models to produce grounded, auditable plans.

---

[![CI](https://github.com/bridge-intelligence-lab/ai-architect/actions/workflows/ci.yml/badge.svg)](https://github.com/bridge-intelligence-lab/ai-architect/actions/workflows/ci.yml) [![Coverage gate](https://img.shields.io/badge/coverage-%E2%89%A575%25-brightgreen.svg)](.github/workflows/ci.yml) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) [![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml) [![Docs](https://img.shields.io/badge/docs-index-blue)](docs/README.md)[![Ruff](https://img.shields.io/badge/lint-ruff-46aef7.svg)](https://github.com/astral-sh/ruff) [![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)

![Hero](docs/images/hero.png)

## Why AI Architect
**AI Architect** is a reference implementation for running LLM and agent services with **production controls**: RBAC, audit trails, cost/FinOps metrics, retrieval, and MLOps, on a FastAPI + ports-and-adapters core. Most portfolio projects show what an LLM service can do; this one focuses on how to **operate** one — who's allowed, what it cost, what it did, and how to prove it.

- **Transparent** by design — audit logs, hashed request/response pairs.
- **Observable** — Prometheus `/metrics` + Grafana dashboards.
- **Cost-aware** — per-request token accounting and FinOps metrics, with real per-model $ cost from LiteLLM's pricing map.
- **Evaluated** — a LangSmith golden dataset, 11 code evaluators + 4 calibrated LLM judges, and config decisions made by experiment (see [Evaluation](#-evaluation)).
- **Governed** — RBAC, retention sweeps, and prompt registries.

> **Project status:** a reference implementation you can run locally. Out of the box the LLM runs in a deterministic offline **stub** unless a provider key is set; retrieval defaults to a **keyword/deterministic baseline** with real **vector retrieval** (Chroma) behind `RAG_BACKEND=vector`; the architect defaults to a structured **deterministic planner** with a **LangGraph tool-loop agent** behind `AGENT_BACKEND=langgraph` (the measured winner on groundedness and latency — see [docs/eval_results/](docs/eval_results/2026-07-04-grid-backend-tokens.md)). Shipped vs planned lives in [docs/MODERNIZATION_PLAN.md](docs/MODERNIZATION_PLAN.md).

---

## 💡 Use Cases
| Scenario | Description |
|-----------|--------------|
| **Architect Assistant** | Ask architectural or implementation questions and receive structured, grounded responses from the system’s own docs. |
| **Policy Navigator** | Explore compliance and governance policies using grounded QA. |
| **PII Remediation** | Detect, redact, and audit sensitive data with explainable steps. |
| **Risk Scoring** | Classify incidents with heuristic or MLflow-tracked models. |
| **MLOps Demonstrator** | Observe model training, drift detection, and registry integration. |

> The **Architect Agent** is the main entry point — all other endpoints act as modular tools or sub-agents.

---

## 🧭 Architect Orchestration Flow
```mermaid
flowchart TD
  subgraph ClientLayer[Client / UI / External API]
    U[User Query]
  end

  subgraph ArchitectLayer[Architect Agent]
    A1[Intent & Mode Selection]
    A2[Planner / Orchestrator]
    A3[Audit & Cost Tracking]
  end

  subgraph Governance[Governance, Observability & Storage]
    DB[(Audit DB)]
    F[FinOps Metrics / Prometheus]
    G[Grafana Dashboards]
    RBAC[RBAC / Security Layer]
  end

  U --> A1 --> A2 --> A3
  A3 --> DB
  A3 --> F --> G
  A3 --> RBAC
```
> Current behavior: `/architect` produces structured plans and citations while emitting audit and metrics events.

---

## ⚡ Quickstart
```bash
# 0) Setup
git clone https://github.com/bridge-intelligence-lab/ai-architect
cd ai-architect
cp .env.example .env
# If you skip .env, export PROJECT_GUIDE_ENABLED=true to enable /architect

# 1) Create environment
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

# 2) Optional: vector RAG (ingest feeds the Chroma store used by RAG_BACKEND=vector)
python scripts/ingest_docs.py   # then set RAG_BACKEND=vector in .env

# 3) Run locally
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4) Query the Architect Agent (guide mode)
curl -sX POST localhost:8000/architect \
  -H "Content-Type: application/json" \
  -d '{"question":"Design a RAG pipeline with drift monitoring"}' | jq .

# Brainstorm mode
curl -sX POST localhost:8000/architect \
  -H "Content-Type: application/json" \
  -d '{"question":"How does the router decide intents?","mode":"brainstorm"}' | jq .
```
**UI:** http://localhost:8000/architect/ui
Note: /architect is feature-gated. Ensure PROJECT_GUIDE_ENABLED=true (in .env or environment) before calling it.

**MCP:** the same capabilities are exposed over the Model Context Protocol
for Claude Desktop / Claude Code / any MCP client — tools `architect_plan`,
`retrieve_docs`, `detect_pii`:

```bash
ai-architect-mcp        # stdio server (or: python -m app.mcp_server)
```

Backend flags apply unchanged (`RAG_BACKEND`, `AGENT_BACKEND`,
`LLM_PROVIDER`). See [ADR-0008](docs/adr/0008-mcp-server.md).

---

## 🧱 Repository Layout
| Folder | Purpose |
|--------|----------|
| `app/routers/` | FastAPI endpoints (architect, query, research, risk, pii, memory) |
| `app/services/` | Core services: RAG, agents, risk, MLflow integration |
| `app/utils/` | Audit, RBAC, cost tracking, prompt registry |
| `db/` | SQLAlchemy models and migrations |
| `ml/` | ML training, drift, and registry scripts |
| `scripts/` | Utilities (ingestion, retention sweep, OpenAPI export) and the eval pipeline (dataset sync, evaluators, judges, experiment grid) |
| `eval/` | Golden prompt dataset (`architect_prompts_v2.jsonl`, 26 prompts) |
| `docs/` | System and feature documentation |

Complete file map → `docs/components.md`

---

## 📚 Documentation
- [Docs index](docs/README.md)
- [Getting started](docs/getting_started.md)
- [API](docs/api.md)
- [Deploy](docs/deploy.md)
- [RAG](docs/rag.md) (vector backends: [docs/rag_vector_backends.md](docs/rag_vector_backends.md))
- [Memory](docs/memory.md)
- [Security](docs/security.md)
- [Observability](docs/observability.md)

## 🧩 System Architecture
```mermaid
flowchart LR
  A["Client / UI"] -->|REST / JSON| B["FastAPI Gateway"]

  subgraph Retrieval_and_Synthesis
    B --> C1["Retriever: DOCS_PATH scan"]
    C1 --> C3["Optional LLM Synthesis"]
    C1 --> C4["Vector Store: FAISS / Chroma"]
  end

  subgraph Memory
    B --> M1["Short-term Memory: SQLite"]
    B --> M2["Long-term Memory: Embeddings"]
  end

  subgraph Governance_and_Compliance
    B --> D1["Audit Logger"]
    D1 --> D2[("Audit DB")] 
    D1 --> D3["Denylist / Compliance Rules"]
    D1 --> D4["Cost Tracker / FinOps Metrics"]
  end

  subgraph Observability
    D4 --> E1["Prometheus /metrics"]
    E1 --> E2["Grafana Dashboard"]
  end

  subgraph ML_Lifecycle
    B --> F1["/predict (MLflow Model API)"]
    F1 --> F2["Model Registry"]
    F1 --> F3["Drift Detector / Retraining"]
  end

  subgraph Agents
    B --> G1["/research (Agent Orchestrator)"]
    G1 --> G2["Search Tool / Web Fetch (allowlist)"]
    G1 --> G3["Summarizer / Risk Checker"]
    G1 --> D1
  end
```


---

## 🧪 Evaluation

Quality is measured, not assumed. The eval stack (all in-repo, reproducible):

- **Golden dataset** — 26 prompts in three sets (grounded core, new features, negative/adversarial hallucination baits), synced idempotently to LangSmith by `scripts/build_langsmith_dataset.py` with per-example expectations as metadata.
- **Rubric** — 11 deterministic code evaluators (`scripts/langsmith_evaluators.py`: structure, citations-match-expectations, truncation, latency) plus 4 LLM judges (`scripts/langsmith_judges.py`: correctness, groundedness, completeness, actionability), calibrated against the codebase ([calibration note](docs/eval_calibration_2026-07-04.md)).
- **Experiments** — `scripts/run_experiment_grid.py` A/B-tests config axes on the same dataset. First grid settled `AGENT_BACKEND` and `LLM_MAX_TOKENS` by measurement: [results + screenshots](docs/eval_results/2026-07-04-grid-backend-tokens.md).

The eval loop has already paid for itself: it caught (and verified the fix for) a LangGraph tool-budget bug that silently returned empty plans, and a retrieval self-pollution bug where eval docs were retrieved as grounding context.

Plan and backlog: [docs/langsmith_test_plan.md](docs/langsmith_test_plan.md), [docs/langsmith_eval_backlog.md](docs/langsmith_eval_backlog.md).

---

## 🔒 Governance & Observability
- **Audit rows** per request (role, hashes, latency, flags)
- **RBAC** via `X-User-Role` (`guest`, `analyst`, `admin`)
- **FinOps**: token & cost metrics at `/metrics`
- **Retention**: `scripts/sweep_retention.py` for old audits
- **Prompt Registry**: versioned YAML under `prompts/`

Full details → `docs/observability.md`, `docs/security.md`

---

## 🗺️ Roadmap (Condensed)
| Phase | Focus | Status |
|-------|--------|--------|
| 0–2 | Core APIs, retrieval (keyword baseline), Audit, Metrics | ✅ Done |
| 3–4 | Orchestration (deterministic planner), RBAC, Grafana, Deploy Recipes | ✅ Done |
| 5–6 | PII detection, Risk ML integration, Router v2 | ✅ Done |
| 7–8 | Memory (short + long term) | ✅ Done |
| 9 | Architect agent on LangGraph (`AGENT_BACKEND=langgraph`) | ✅ Done |
| 10 | Real vector retrieval (`RAG_BACKEND=vector`), LiteLLM cost tracking, MCP server | ✅ Done |
| 11 | Presidio PII backend, CI coverage gate | ✅ Done |
| 12+ | Pinecone backend, role-scoped MCP, memory in the LangGraph loop | 🧩 Planned |

> Full roadmap and build-vs-buy rationale: [docs/MODERNIZATION_PLAN.md](docs/MODERNIZATION_PLAN.md), [ADR-0004](docs/adr/0004-build-vs-buy.md).

---

## 🤝 Contributing
1. Interact with the **Architect Agent** in brainstorm mode.  
2. Copy generated plans into GitHub issues.  
3. Follow `CONTRIBUTING.md` for PR flow.

Starter prompts → `docs/llm_agent_streaming_prompts.md`

---

## 🧭 License
Apache-2.0. See `LICENSE`.

