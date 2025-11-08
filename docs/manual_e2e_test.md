# Manual End-to-End Test Plan

This guide walks you through a comprehensive, reproducible end-to-end (E2E) test of the AI Architect. It combines manual validation with scripted commands (curl/Python) and optional stress testing.

Prerequisites
- Python 3.11+
- POSIX shell (bash)
- curl and jq installed (required for the script)
  - Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y jq`
  - macOS (Homebrew): `brew install jq`
  - Fedora: `sudo dnf install -y jq`
- Optional: GNU parallel or xargs (for stress)

Setup
1) Create venv and install
```
python -m venv .venv
. .venv/bin/activate
pip install -e .
```
2) Start the API (choose one)
- Option A (recommended for this guide): from another terminal
```
. .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- Option B: let the provided script start the server (see scripts/manual_e2e_test.sh --start-server)

3) Prepare environment
- Minimal defaults are fine. You can customize flags during steps.

Test flow overview (ordered)
1. Health and metrics
2. Query — ungrounded baseline
3. Query — grounded with citations
4. Router — intent selection
5. PII endpoint
6. Risk scoring (heuristic and ML modes)
7. Memory — short-term (list, clear)
8. Memory — long-term (list, clear)
9. Agents — research pipeline
10. RAG flags (multi-query, hyDE)
11. Observability (audit row, metrics counters)
12. OpenAPI export
13. Optional stress tests

Validation methodology
- Each step includes: commands to run, what to expect, what to check in outputs. The script performs basic assertions (grounded citations non-empty, PII RBAC 403 check, conditional memory clear semantics).
- Save outputs in ./e2e_logs/<timestamp> (the script does this automatically). Each run folder contains trace.log and per-step .out files.

---

Step 1: Health and metrics
Commands
```
curl -sS localhost:8000/healthz | jq .
```
Expected
- 200 OK and a simple JSON (e.g., {"status":"ok"} or similar).

Commands
```
curl -sS localhost:8000/metrics | head -n 50
```
Expected
- Prometheus text format. Look for process_*, python_*, and custom app metrics.

---

Step 2: Query — ungrounded baseline
Commands
```
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello there","grounded": false}' | jq .
```
Expected
- 200 OK
- answer present (stub ok), citations may be empty (ungrounded)
- audit has request_id, rag_backend=langchain

---

Step 3: Query — grounded with citations
Prepare docs
```
mkdir -p e2e_docs
printf "GDPR is a regulation about data protection." > e2e_docs/gdpr.txt
export DOCS_PATH=$PWD/e2e_docs
```
Commands
```
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -H 'X-User-Role: analyst' \
  -d '{"question":"What is GDPR?","grounded": true}' | jq .
```
Expected
- 200 OK
- citations is a non-empty list
- audit.rag_backend == "langchain"

---

Step 4: Router — intent selection
Enable router
```
export ROUTER_ENABLED=true
```
PII detect
```
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"Email is bob@example.com","grounded": false}' | jq .
```
Expected: audit.router_intent == "pii_detect"

Risk score
```
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the risk score for this incident?","grounded": false}' | jq .
```
Expected: audit.router_intent == "risk_score"

Policy navigator
```
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"What policy covers encryption?","grounded": false}' | jq .
```
Expected: audit.router_intent == "policy_navigator" (or qa if not matched)

---

Step 5: PII endpoint
```
curl -sS -X POST localhost:8000/pii \
  -H 'Content-Type: application/json' \
  -H 'X-User-Role: analyst' \
  -d '{"text":"Contact me at alice.smith+test@example.org and +1 416-555-1212","include_citations": false}' | jq .
```
Expected
- pii.types_present contains email and phone
- masked previews in entities

Optional locales
```
export PII_LOCALES="US,UK,CA"
```

---

Step 6: Risk scoring
Heuristic
```
curl -sS -X POST localhost:8000/risk \
  -H 'Content-Type: application/json' \
  -H 'X-User-Role: analyst' \
  -d '{"text":"Critical breach and violation, potential lawsuit"}' | jq .
```
Expected: label==high, audit contains risk_score_value

ML-like mode
```
export RISK_ML_ENABLED=true
export RISK_THRESHOLD=0.6
curl -sS -X POST localhost:8000/risk \
  -H 'Content-Type: application/json' \
  -H 'X-User-Role: analyst' \
  -d '{"text":"Critical incident with severe impact and vulnerability exposed."}' | jq .
```
Expected: audit.risk_score_method == "ml", value in [0,1]

---

Step 7: Memory — short-term
Enable
```
export MEMORY_SHORT_ENABLED=true
```
Drive context
```
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"hello","user_id":"u","session_id":"s"}' | jq .
```
List
```
curl -sS "localhost:8000/memory/short?user_id=u&session_id=s" \
  -H 'X-User-Role: analyst' | jq .
```
Clear
```
curl -sS -X DELETE "localhost:8000/memory/short?user_id=u&session_id=s" \
  -H 'X-User-Role: analyst' | jq .
```
Expected: cleared==true

---

Step 8: Memory — long-term
Enable
```
export MEMORY_LONG_ENABLED=true
```
Drive one query (the server injects a deterministic long fact when enabled)
```
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"A long message to seed long memory","user_id":"lu"}' | jq .
```
List
```
curl -sS "localhost:8000/memory/long?user_id=lu" -H 'X-User-Role: admin' | jq .
```
Clear
```
curl -sS -X DELETE "localhost:8000/memory/long?user_id=lu" -H 'X-User-Role: admin' | jq .
```
Expected: cleared==true

---

Step 9: Agents — research
```
curl -sS -X POST localhost:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"topic":"Latest updates on GDPR and AI","steps":["search","fetch","summarize","risk_check"]}' | jq .
```
Expected
- findings array present
- audit.steps include each step with latency/hash

---

Step 10: RAG flags (multi-query, hyDE)
```
export RAG_MULTI_QUERY_ENABLED=true
export RAG_MULTI_QUERY_COUNT=4
export RAG_HYDE_ENABLED=true
curl -sS -X POST localhost:8000/query \
  -H 'Content-Type: application/json' \
  -H 'X-User-Role: analyst' \
  -d '{"question":"What is data retention?","grounded": true}' | jq .
```
Expected
- citations non-empty
- audit includes rag_multi_query=true, rag_multi_count>=1, rag_hyde=true

---

Step 11: Observability
Audit persistence (optional)
- Check sqlite DB (if DB_URL is default sqlite):
```
sqlite3 audit.db 'select count(1) from audit;'
```
Metrics counters
```
curl -sS localhost:8000/metrics | grep '^app_tokens_total' -n | head -n 3
```
Expected: tokens_total appears and increases after requests

---

Step 12: OpenAPI export
```
. .venv/bin/activate
python scripts/export_openapi.py
ls -l docs/openapi.yaml
```
Expected: docs/openapi.yaml exists and contains /query, /pii, /risk, /research

---

Step 13: Optional stress tests
Option A: Bash loop
```
for i in $(seq 1 50); do \
  curl -sS -X POST localhost:8000/query -H 'Content-Type: application/json' \
    -d '{"question":"Hello '"$i"'","grounded": false}' >/dev/null & done; wait
```
Option B: Python asyncio (see scripts/e2e_helpers.py)

Validate
- No 5xx responses
- Latency reasonable (watch server logs)
- Metrics counters increased

Troubleshooting
- If grounded queries return 403, ensure the header X-User-Role: analyst is set.
- If citations are empty, check DOCS_PATH and that files exist.
- If /pii returns 403, add X-User-Role: analyst header.
- If metrics protected, set METRICS_TOKEN and pass X-Metrics-Token.
