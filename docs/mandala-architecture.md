# 🧭 AI Architect + Mandala Roadmap

**Last Updated:** 2025-10-20  
**Author:** Rodrigo Oliveira  

---

## 🎯 Project Overview

This roadmap defines the phased development plan for integrating **AI Architect** with **Mandala** — a modular actor-based world engine — to create a platform for multi-agent simulations across domains like:

- 👩‍💻 **Dev Team Collaboration** (Agile workflow)
- 🕺 **Night-Out Social Behavior**
- 💹 **Hedge Fund Decision-Making**

The long-term vision is a unified framework where:

- **AI Architect** owns the *workflows, cognition, and LLM orchestration*.
- **Mandala** owns the *world state, time, event persistence, and tool execution*.
- Communication happens through a **functional message contract**, not scenario-specific APIs.

---

## 🧩 Architectural Principle

| Layer | Responsibility | Key Tech |
|-------|----------------|----------|
| **AI Architect** | Cognition, workflows, cost & audit, memory, RAG | FastAPI, CrewAI or LangGraph, LiteLLM gateway |
| **Mandala** | Time, actor supervision, persistence, tools | Akka/Pekko, QuestDB, Redis, Qdrant |
| **LLM Infrastructure** | Local inference + routing | vLLM / TGI, LiteLLM, Ollama |
| **Dashboard** | Real-time telemetry | Vue + QuestDB |
| **Data Services (Finance)** | Offline/online features | Feast for Finance, Redis, Parquet |

---

## 🧱 Functional Message Contract

All workflows communicate via a scenario-agnostic JSON schema.

### Message Types
- **ThinkRequest** – Mandala → AI Architect: “decide what to do next.”
- **Action** – AI Architect → Mandala: tool calls, messages, or world interactions.
- **ToolResult** – Mandala → AI Architect: results of executed tools.
- **WorldEvent** – Mandala → AI Architect: external events, broadcasts.
- **MemoryOp** – Either direction: read/write long-term memory.

This neutral contract keeps Architect scenario-agnostic and allows independent evolution of workflows and world logic.

---

## 🚀 Phased Development Plan

### **Phase 1 — Local LLM Infrastructure Setup**
**Goal:** Establish reliable, low-cost inference and routing.

**Deliverables**
- `vLLM` or `TGI` running **Llama-3 8B** or **Qwen 2.5 7B/14B** on the 3080 Ti.
- `LiteLLM` gateway routes: `/generate`, `/embed`, `/judge`.
- `Ollama` or `llama.cpp` for local tests.
- Shared **Redis + QuestDB** for cache and metrics.
- Basic FastAPI test endpoint (`/hello_llm`).

**Outcome:** Baseline latency, throughput, and cost.  
_No business logic yet — just plumbing._

---

### **Phase 2 — Proof of Concept (Dev-Team Scenario)**
**Goal:** Validate the integration between AI Architect (brains) and Mandala (world).

**Deliverables**
- Workflow pack inside AI Architect (CrewAI/LangGraph)  
  Roles: *Dev, QA, Reviewer, Scrum Master*  
  Graph: `receive_ticket → plan → code → test → review → report`
- Mandala prototype with simulated repo tools (`edit_file`, `run_tests`, `review_pr`).
- Implement message contract (`ThinkRequest`, `Action`, `ToolResult`, etc.).
- Vue dashboard + QuestDB telemetry.

**Outcome:**  
✅ Validated end-to-end loop (LLM → Action → Tool → Result → Next Step).  
✅ Real telemetry for analysis.

**Decision:**  
If the integration is stable, promote this to **MVP** quality instead of rewriting later.

---

### **Phase 3 — MVP (Minimum Viable Platform)**
**Goal:** Harden architecture, modularize, and prepare for new scenarios.

**Deliverables**
- Split repositories:
  - `mandala-core` — actors, tools, event log.
  - `ai-architect` — workflow packs, cognition service.
- Docker-Compose or Helm deployment including:  
  `vllm`, `LiteLLM`, `Architect`, `Mandala`, `QuestDB`, `Qdrant`, `Redis`.
- Add persistence (event sourcing) + replay.
- Formalize functional message contract (versioned).
- Unit tests mocking ToolResults to run workflows without Mandala.
- Grafana dashboards for cost/latency/tool metrics.

**Outcome:**  
Reusable, production-ready skeleton where new workflows plug in cleanly.

---

### **Phase 4 — Multi-Scenario Expansion**
**Goal:** Onboard a new development team to extend platform to additional domains.

**Deliverables**
- “Workflow Pack Template” inside AI Architect.
- Documentation for message contracts and tool registration.
- Scenarios:
  1. **Night Out** — social agents, venues, proximity rules.  
  2. **Hedge Fund** — integrates **Feast for Finance**; roles: PM, Research, Trader, Risk, Compliance.
- CI/CD pipelines, deterministic replay, and regression suite.

**Outcome:**  
Platform demonstrates domain-agnostic extensibility and team scalability.

---

## ⚖️ Value of Mandala Integration

| Feature | Architect-Only | Architect + Mandala |
|----------|----------------|--------------------|
| Deterministic time & replay | Limited | ✅ Full event sourcing |
| Concurrency control | Async I/O | ✅ Actor backpressure |
| Fault tolerance | App-level | ✅ Supervision trees |
| Simulation realism | Mocked | ✅ Realistic tool physics |
| Scaling agents | Moderate | ✅ High |
| Setup complexity | Low | Higher (one more service) |

**Rule of Thumb**
- *Exploration & prototype* → Architect-only.  
- *Production-like simulations* → Architect + Mandala.

---

## 🗓️ Suggested Timeline (approx.)

| Phase | Duration | Key Outcome |
|-------|-----------|-------------|
| 1 | 2 weeks | Local inference infra live |
| 2 | 3 weeks | Dev-team workflow validated |
| 3 | 4 weeks | MVP platform with replay & dashboards |
| 4 | ongoing | New scenarios by extended dev team |

---

## 🔩 Next Steps

1. Finalize the **functional message contract** schema.  
2. Implement `/think`, `/tool-result`, and `/world-event` endpoints.  
3. Stand up Phase 1 infra (vLLM + LiteLLM + QuestDB).  
4. Build Dev-Team workflow pack and validate the loop.  
5. Transition to MVP without discarding code.  
6. Prepare documentation for new teams to add scenarios.

---

## 💬 Notes

- **AI Architect** can run standalone (mocked tools) for demos.  
- **Mandala** becomes essential for time-based, replayable, multi-agent simulations.  
- The roadmap keeps both paths compatible via the **functional contract**.

---

*End of Roadmap*



```mermaid

flowchart LR
  %% ========= NODES =========
  subgraph Client["AI Architect - Workflows & Cognition"]
    A1[/CrewAI or LangGraph - FastAPI: /think /tool-result /world-event/]
    A2[[Policies & Rubrics - Cost / Audit]]
    A3[[Vector / RAG Memory]]
  end

  subgraph Proxy["TensorBook - 3080 Ti GPU - Inference & Proxy"]
    L1[[LiteLLM Proxy - :4000 /v1/*]]
    V1[[vLLM - Qwen 7B Instruct - GPU FP16 - :8000 /v1]]
    O1[[Ollama - CPU - nomic-embed-text, deepseek-coder - :11434]]
    C1[[HF Cache]]
    C2[[vLLM Compile Cache]]
  end

  subgraph World["Mandala - Akka or Pekko World Engine"]
    M1[/Actors - Agents, Scheduler, Mailboxes/]
    M2[[MCP Tools Layer]]
    M3[[Event Log -> QuestDB]]
  end

  subgraph Data["Shared Services"]
    Q1[[QuestDB - Telemetry / Events]]
    R1[[Redis - Cache / Queues]]
    VDB[[Qdrant - Long-term Memory]]
    PG[[Postgres or SQLite - Relational State]]
  end

  UI[Vue Dashboard - Real-time Metrics]

  %% ========= LINKS =========
  %% Architect <-> Proxy
  A1 -- chat or JSON --> L1
  L1 -- route: local-generate --> V1
  L1 -- route: local-embed --> O1
  L1 -- route: local-code --> O1

  %% Proxy caches
  V1 --- C1
  V1 --- C2

  %% Architect <-> World
  A1 -- Action or ToolCall --> M2
  M2 -- ToolResult or WorldEvent --> A1
  A2 --> A1
  A3 <--> VDB

  %% World persistence + telemetry
  M1 --> M2
  M1 -- emit events --> M3
  M3 --> Q1
  M1 <--> PG
  L1 --> Q1
  L1 <--> R1

  %% Dashboard
  UI --- Q1

  %% Optional future split
  subgraph Optional["Jarvis - 1080 Ti GPU - Future Node"]
    OJ[[Ollama - GPU or CPU]]
  end
  OJ -. move embeddings or code later .-> L1

  %% Styles
  classDef svc fill:#0b7285,stroke:#064e63,color:#fff
  classDef store fill:#364fc7,stroke:#243a8f,color:#fff
  class A1,A2,A3,L1,V1,O1,M1,M2,M3,UI,OJ svc
  class Q1,R1,VDB,PG,C1,C2 store

```

```mermaid
sequenceDiagram
  autonumber
  participant Mandala as Mandala Agent - Actor
  participant Architect as AI Architect - /think
  participant LiteLLM as LiteLLM Proxy - :4000
  participant vLLM as vLLM - Qwen 7B - :8000
  participant Ollama as Ollama - CPU - :11434
  participant Tools as MCP Tools
  participant QuestDB as QuestDB - Telemetry

  Note over Mandala,Architect: Functional contract - scenario agnostic
  Mandala->>Architect: ThinkRequest - agent, objective, context, tools, budgets
  Architect->>LiteLLM: ChatCompletion - model=local-generate
  LiteLLM->>vLLM: /v1/chat/completions
  vLLM-->>LiteLLM: tokens and response
  LiteLLM-->>Architect: completion and usage
  Architect->>Mandala: Action list - tool_call static_check

  Mandala->>Tools: Execute tool_call
  Tools-->>Mandala: ToolResult - json
  Mandala->>Architect: ToolResult - call_id and result
  Architect->>LiteLLM: Embedding - model=local-embed
  LiteLLM->>Ollama: /api/embeddings
  Ollama-->>LiteLLM: vector
  LiteLLM-->>Architect: embedding

  Architect->>Mandala: Next Action - say / approve / more tools
  Mandala->>QuestDB: log - latency, tokens, tool stats
  LiteLLM->>QuestDB: log - route, usage, errors
  Note over Mandala: Tick advances - repeat until turn complete

```