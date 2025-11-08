# AI Agent Stack – Flowise → CrewAI → LangGraph → FastAPI

```mermaid
flowchart TB

%% ==== LAYERS ====
subgraph UI
  A[Next.js / Streamlit Portal]
  B[Ops Dashboard]
end

subgraph API_Gateway
  L[FastAPI / LangServe]
end

subgraph Orchestration
  C[LangGraph Orchestrator]
  D[(State Store - Redis/SQLite/Postgres)]
  E[Task Queue - RQ/Celery]

  %% Agents nested inside Orchestration
  subgraph Agents
    F[CrewAI - Coordinator]
    G[Research Agent]
    H[Trader Agent]
    I[Risk Agent]
    J[Data Agent]
  end
end

subgraph Tools_APIs
  K[LangChain Tools]
  K1[Broker APIs - MT5 / IBKR]
  K2[QuantConnect API]
  K3[Market Data - Polygon / Alpaca]
  K4[Docs + KB - RAG]
end

subgraph Services
  M[Vector DB - Pinecone / FAISS]
  N[MLflow / Weights & Biases]
  O[(Operational DB - Postgres)]
end

subgraph Prototyping
  P[Flowise - Visual Builder]
  Q[LangFlow - Optional]
end

subgraph Execution
  X[Kubernetes / Docker]
  Y[Observability - OpenTelemetry + Grafana]
end

%% ==== FLOWS ====
A -->|user actions| L
B -->|runbooks + control| L
L -->|invoke| C
C <--> D
C --> E

%% CrewAI multi-agent team
C -->|run plan| F
F --> G
F --> H
F --> I
F --> J

%% Tools + data
G --> K4
J --> K3
H --> K1
H --> K2
K4 --> M
K3 --> O

%% Tracking + experiments
C --> N
H --> N
J --> N

%% Prototyping to prod
P -->|export flow| C
Q -->|python nodes| C

%% Runtime + ops
C --> X
L --> X
X --> Y
```

---

### Notes

* **Agents** are now visually **nested under the Orchestration** layer for a clearer vertical hierarchy.
* **Flowise** for rapid prototyping of chains/agents; export flows to **LangGraph** for deterministic, stateful orchestration.
* **CrewAI** models the human-like team (Coordinator → Research / Trader / Risk / Data) while **LangGraph** controls retries, branching, checkpointing.
* **FastAPI/LangServe** exposes clean endpoints to the portal and external systems.
* **Observability** (OpenTelemetry + Grafana) instruments the graph, agents, and tool calls.
* **Experiment tracking** via MLflow or Weights & Biases.
* **Deploy** on Docker/Kubernetes; use Redis or Postgres for state and queues.
