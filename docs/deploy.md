---
title: Deployment quick notes
status: current
module: ops
last_reviewed: 2026-07-04
source:
  - docker-compose.yml
---

# Deployment quick notes

This project is designed to run locally or on simple PaaS setups. Below are minimal notes; tailor for your platform.

## Render (Docker)

- Push your repo to GitHub
- Create a new Web Service and choose Dockerfile at repo root
- Set environment variables (see .env.example)
- Health check path: /healthz
- (Optional) Add a persistent disk mounted at /data for audit.db and vectorstore

## Fly.io (example)

- Create an app and deploy with Dockerfile
- Expose port 8000, set health check to /healthz
- Use volumes for persistence (/data)

## Cloud Run (example)

- Build container and deploy
- Set concurrency to a small number for local CPU-friendly workloads
- Set env vars and health check

## Validation

- After deploy, run a few smoke tests:

```bash
# Health
curl -s $URL/healthz

# Query (ungrounded)
curl -s -X POST "$URL/query" -H "Content-Type: application/json" -d '{"question":"What is GDPR?","grounded":false}'

# Metrics (if open)
curl -s $URL/metrics | head -n 40
```
