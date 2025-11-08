# 🧩 AI Architect x Mandala Integration – Implementation Plan

**Document purpose:**  
This file explains the context, overall plan, and actionable tasks for implementing the integrated **AI Architect + Mandala** platform — following the design captured in `mandala-architecture.md` and the multi-phase roadmap.

**Owner:** Rodrigo Oliveira  
**Last updated:** 2025-10-20  

---

## 1. Project Context

**AI Architect** is the cognition and orchestration layer for multi-agent systems — hosting LLM workflows, cost governance, and audit logic.  
**Mandala** is a modular actor-based runtime that manages time, concurrency, and world simulation.  
Together they form a platform capable of modeling social, technical, and financial team dynamics.

The project’s first use case is the **Dev-Team Simulation**, later expanding to **Night-Out** and **Hedge-Fund** scenarios.  
All three share a **functional message contract** so the world (Mandala) and cognition (Architect) remain domain-agnostic.

---

## 2. Architecture at a Glance

| Layer | Responsibilities | Tech Stack |
|-------|------------------|-------------|
| **AI Architect** | LLM calls, reasoning graphs (CrewAI/LangGraph), memory (Qdrant), audit, cost tracking | FastAPI, Python, LiteLLM, vLLM |
| **Mandala** | Actor scheduling, world clock, event sourcing, tool execution, supervision trees | Akka/Pekko (Scala/Java) |
| **Data / Infra** | Metrics, memory, caching, feature store | QuestDB, Redis, Qdrant, Feast |
| **UI / Monitoring** | Visualization, replay control, dashboards | Vue + Grafana |

**Integration principle:**  
All communication flows through a **functional message schema** (ThinkRequest, Action, ToolResult, WorldEvent, MemoryOp).  
This guarantees loose coupling and supports testing AI Architect workflows without running Mandala.

---

## 3. Execution Phases

### **Phase 1 — Local LLM Infrastructure**
**Objective:** Stand up the local inference stack.

**Tasks**
1. Configure **vLLM** with Llama-3 8B or Qwen 2.5 7B on 3080 Ti.  
2. Install **LiteLLM** gateway and expose `/generate`, `/embed`, `/judge`.  
3. Deploy **QuestDB** and **Redis** containers for metrics and cache.  
4. Add FastAPI “hello” endpoint to confirm token logging.  
5. Benchmark latency and throughput; document in `docs/perf-baseline.md`.

**Deliverable:** Stable local inference environment with telemetry.

---

### **Phase 2 — Dev-Team POC**
**Objective:** Validate integration between AI Architect and Mandala.

**Tasks**
1. Implement workflow pack in AI Architect:  
   - Roles: Dev, QA, Reviewer, Scrum Master  
   - LangGraph nodes: `plan → code → test → review → report`
2. Implement Mandala prototype:  
   - Actor hierarchy, tick scheduler, simple MCP tool handlers (`edit_file`, `run_tests`, `review_pr`)  
   - HTTP endpoints `/think`, `/tool-result`, `/world-event`
3. Connect both via JSON contract (ThinkRequest ↔ Action ↔ ToolResult).  
4. Log all exchanges to QuestDB.  
5. Build basic **Vue dashboard** for per-agent telemetry (tokens/sec, latency, cost).

**Deliverable:** Working E2E simulation demonstrating message flow and telemetry.

---

### **Phase 3 — MVP Platform**
**Objective:** Harden architecture and modularize for reuse.

**Tasks**
1. Split repositories (or modules):  
   - `mandala-core`  
   - `ai-architect`  
   - `shared-contracts`
2. Introduce **event sourcing** in Mandala; persist events for replay.  
3. Implement **replay controller** and snapshot mechanism.  
4. Add **Grafana dashboards** (latency, cost, tool success).  
5. Package with **docker-compose.yml** (vLLM, LiteLLM, Mandala, Architect, QuestDB, Qdrant, Redis).  
6. Write unit tests mocking ToolResults (Architect runs stand-alone).  
7. Update `mandala-architecture.md` diagrams to reflect final message paths.

**Deliverable:** Reusable platform capable of running multiple scenarios deterministically.

---

### **Phase 4 — Scenario Expansion**
**Objective:** Extend to additional use cases and onboard new dev team.

**Tasks**
1. Provide **Workflow Pack Template** inside AI Architect.  
2. Document contract schemas and tool registration.  
3. Implement:
   - **Night-Out Scenario** (social agents, venues, events)
   - **Hedge-Fund Scenario** (integrate **Feast for Finance**, add PM, Research, Trader, Risk roles)
4. Add CI/CD pipelines and deterministic replay tests.  
5. Publish developer documentation (`docs/dev-guide.md`).

**Deliverable:** Full multi-scenario platform demonstrating extensibility.

---

## 4. Ownership of LLM Communication

AI Architect remains the **sole communicator with LLMs** through the LiteLLM gateway.

**Rationale**
- Centralized governance (cost limits, safety, prompt templates)
- Consistent model routing (local vs API)
- Simplified observability and audit trails
- Negligible latency cost (<5 ms over LAN)

Mandala executes deterministic rules and tools; only Architect performs reasoning and generation.

---

## 5. Infrastructure & Deployment

| Component | Host | Notes |
|------------|------|-------|
| vLLM + LiteLLM | RTX 3080 Ti workstation | Main inference server |
| Ollama / Embeddings | GTX 1080 Ti desktop | Embeddings + rerankers |
| QuestDB, Redis, Grafana | Shared Docker network | Metrics + cache |
| AI Architect + Mandala | Same LAN / docker-compose | Communicate via HTTP/gRPC |
| Vue Dashboard | Dev laptop | Real-time telemetry |

---

## 6. Deliverables Summary

| Phase | Deliverable | Owner |
|-------|--------------|-------|
| 1 | Local LLM stack operational | Rodrigo |
| 2 | Dev-Team workflow + dashboard | Core dev |
| 3 | MVP platform with replay & modular repos | Core dev |
| 4 | Night-Out + Hedge-Fund scenarios | New dev team |

---

## 7. Immediate Next Tasks

1. Finalize and commit the **functional message contract** (`/contracts/messages.json`).  
2. Add **/think** endpoint in AI Architect (FastAPI → LangGraph).  
3. Implement minimal **Mandala HTTP client** to post ThinkRequests.  
4. Stand up Phase 1 infra via `docker-compose`.  
5. Run the Dev-Team POC end-to-end and record metrics in QuestDB.  
6. Update `mandala-architecture.md` diagrams with actual endpoint URLs.  
7. Create GitHub Project board with milestones matching the four phases.

---

## 8. References

- `docs/mandala-architecture.md` — architecture diagrams and roadmap  
- `README.md` — project overview  
- `feast-for-finance` repository — financial feature pipeline  
- `AI-Architect` repository — cognition, governance, and audit layer  

---

**End of Document**
