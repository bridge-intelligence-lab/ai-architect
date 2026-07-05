---
title: Security
status: current
module: governance
last_reviewed: 2026-07-04
source:
  - app/utils/rbac.py
---

# Security

## RBAC

- Roles: guest, analyst, admin
- Header: X-User-Role (unknown/missing -> guest)
- Route policies (summary):
  - /metrics: open by default; token required if METRICS_TOKEN is set
  - /predict: analyst/admin
  - /query: grounded=true requires analyst/admin; grounded=false allows guest
  - /research steps: fetch/search/summarize -> analyst+; risk_check -> guest+

## Metrics exposure

- Protect /metrics in production by setting METRICS_TOKEN and configuring Prometheus to send the header.

## Secrets

- No secrets in code.
- Use environment variables or secret managers; see .env.example.

## Logging

- JSON logs include request_id and exception info; avoid logging sensitive payloads.
