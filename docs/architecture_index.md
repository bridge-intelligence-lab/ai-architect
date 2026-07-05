---
title: Architecture index
status: current
module: architecture
last_reviewed: 2026-07-04
---

# Architecture index

This document orients the Architect use case by linking core components, endpoints, env flags, and flows.

## Core endpoints and roles

- /query: RAG QA, optional router intents
- /pii: PII detection and remediation helpers
- /risk: Heuristic risk scoring (ML mode paused)
- /research: Research agent with safety and denylist controls
- /memory/short and /memory/long: conversational memory stores
- /metrics, /healthz: observability and health

## Router concepts

- Enable with ROUTER_ENABLED=true
- Configure with ROUTER_RULES_JSON or ROUTER_RULES_PATH; backend is rules v2
- Intents: qa, pii_detect, risk_score, policy_navigator, pii_remediation, other

## RAG flags

- RAG_MULTI_QUERY_ENABLED, RAG_MULTI_QUERY_COUNT
- RAG_HYDE_ENABLED
- DOCS_PATH to select corpus

## Memory model

- Short memory: capped + pruning semantics; clear endpoints
- Long memory: retention and list/clear endpoints
- RBAC enforced for memory operations

## Observability

- Prometheus /metrics (optionally protected by METRICS_TOKEN)
- OpenAPI export script and Grafana dashboards

## Use case mapping checklist

- Define intent (QA vs PII vs Risk vs Research)
- Choose grounded=true when you need citations
- Identify env flags to enable features
- Outline endpoints and services to modify
