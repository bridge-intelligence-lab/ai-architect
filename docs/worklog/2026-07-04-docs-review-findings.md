# ai-architect docs review — 2026-07-04 (full-power pass)

Method: 4 subagent auditors (README/entry, .env.example, RAG docs, agent docs) + inline audit of
testing/architecture/root/api/observability clusters + skeptic spot-verification of the highest-impact
claims (dead env vars, ports, defaults all re-confirmed by grep). ~56 findings total.
Severity: contradiction = doc says X, code does not-X · stale = superseded · gap = shipped but undocumented · nit.

## Tier 1 — contradictions (doc actively wrong, fix first)

1. **getting_started.md:49** Grafana URL says :3000; compose maps `"3001:3000"` (docker-compose.yml:48). → say :3001.
2. **docs/rag.md:35 + .env.example:14** `DOCS_PATH` divergent defaults: query/keyword path defaults `./examples`
   (doc_retriever.py:186, query.py:136), ingest script defaults `./docs` (ingest_docs.py:16). Unset = ingest one
   corpus, scan another. → document both defaults, recommend setting explicitly.
3. **docs/config.md:9** DB_URL default documented as `sqlite:////data/audit.db`; code is `sqlite:///./audit.db`
   (db/session.py:13).
4. **docs/config.md:13** `EMBEDDINGS_MODEL` doesn't exist; real vars are `LOCAL_EMBEDDING_MODEL` /
   `OPENAI_EMBEDDING_MODEL` (rag_retriever.py:25,48).
5. **getting_started.md:63-80** LiteLLM-gateway section built on `LLM_API_KEY` / `EMBEDDINGS_MODEL` — neither read
   anywhere; app uses `OPENAI_API_KEY`, native LiteLLM routing (llm_client.py:15-16,59-68).
6. **.env.example:23-24** comment says "defaults keep offline stub" then sets `LLM_PROVIDER=openai`. Copying the
   example does NOT keep the stub.
7. **capabilities_current.md:106-110** lists MCP server and vector-DB backends as "Out of scope (to design next)" —
   both shipped (app/mcp_server.py, vector_retriever.py). Same doc line 31 describes /pii as regex-only; presidio
   backend shipped (pii.md documents it correctly).
8. **docs/testing.md coverage section** coverage shown as optional with `--cov=app --cov=ml --cov=db`; CI enforces
   `--cov=app --cov=scripts --cov-fail-under=75` (ci.yml:32). The gate is undocumented under docs/ — the exact gap
   that made eval prompt B8 unanswerable.
9. **rag_vector_backends.md:14-16** claims LC_* flags "gone from the docs" while getting_started.md:42,60 and
   ports_and_adapters.md:31-32,75-76 still document `LC_RAG_BACKEND` / `RAG_BACKEND=langchain|llamaindex|haystack`
   (none exist in code).

## Tier 2 — dead or no-op config in .env.example

10. `LC_RAG_ENABLED` (line 10) — read nowhere. Delete.
11. `LLM_ENABLE_RESEARCH` (line 30) — read nowhere (/research always runs; only QUERY/ARCHITECT flags exist). Delete or implement.
12. `PII_REMEDIATION_INCLUDE_SNIPPETS` (line 58) — read nowhere; controlled per-request by `return_snippets`. Delete or wire.
13. `LANGCHAIN_TRACING_SESSION_NAME` (line 69) — read only into a log line; LANGCHAIN_PROJECT is what names the project (architect_agent.py:168-170). Drop or wire.
14. `MLFLOW_EXPERIMENT_NAME=ai-monitor` (line 65) — code default is `ai-architect`; example silently switches experiments.
15. `LANGCHAIN_TRACING_V2=true` no-op without LANGCHAIN_API_KEY (blank in example) — comment it.
16. OPENROUTER/AZURE keys consumed by LiteLLM, not app code — keep with a comment.

## Tier 3 — missing from .env.example (shipped flags)

17. `AGENT_BACKEND` (builtin|langgraph, default builtin — architect_agent.py:50)
18. `RAG_BACKEND` (keyword_scan|vector — doc_retriever.py:188)
19. `PII_BACKEND` (+ PII_PRESIDIO_THRESHOLD 0.5, PII_SPACY_MODEL — pii_detector.py:114, pii_presidio.py:42,53)
20. `RAG_EXCLUDE_FILES` (doc_retriever.py:31)
21. `EVAL_JUDGE_MODEL` (default gpt-4.1-mini — langsmith_judges.py:18)
22. Research safety: `AGENT_LIVE_MODE`, `AGENT_URL_ALLOWLIST`, `DENYLIST` (agent.py:12-14)
23. Router: `ROUTER_RULES_JSON`, `ROUTER_RULES_PATH`, `ROUTER_BACKEND` (router.py:22-23,128)
24. Risk: `RISK_ML_ENABLED`, `RISK_THRESHOLD` (risk_scorer.py:97-99)
25. MLflow serving: `MLFLOW_MODEL_URI`, `MLFLOW_MODEL_ARTIFACT_PATH`, `MLFLOW_FEATURE_ORDER_ARTIFACT`, `MLFLOW_MODEL_CACHE_TTL` (mlflow_client.py)
26. Embeddings: `LOCAL_EMBEDDING_MODEL`, `OPENAI_EMBEDDING_MODEL`, `RAG_COLLECTION`

## Tier 4 — README / entry-point staleness

27. **README.md:19** status paragraph: "vector retrieval is next on the roadmap", "LangGraph agent is on the
    roadmap" — both shipped; contradicts its own roadmap table (198-199). THE first-impression bug.
28. **README.md:16** "real per-model $ cost via LiteLLM is on the roadmap" — shipped (llm_client.py:56).
29. **README.md:196** roadmap phase 5-6 (PII, Risk ML, Router v2) marked 🚧 In Progress — all shipped.
30. **README (whole)** no Evaluation section: golden dataset, 15-metric rubric, judges, experiment grid, results
    doc all invisible. Add section + link docs/eval_results/, add eval scripts to repo-layout table (line 118).
31. **README quickstart + getting_started.md:22-24** `ingest_docs.py` step inert without `RAG_BACKEND=vector` — say so.
32. **getting_started.md:13** clone URL wrong org (rodrigo-fonseca-oliveira vs bridge-intelligence-lab).
33. **getting_started.md:42,60** LC_RAG_BACKEND / "LangChain mode" — dead vocabulary, replace with RAG_BACKEND=vector.
34. **docs/config.md (whole)** missing every headline flag (AGENT_BACKEND, RAG_BACKEND, PII_BACKEND,
    RAG_EXCLUDE_FILES, LLM_*, PROJECT_GUIDE_ENABLED); line 29 claims .env.example is "complete" — it isn't.

## Tier 5 — stale planning docs (mark superseded, don't rewrite history)

35. **docs/architect_deterministic_mode.md** whole doc proposes a LangGraph design that never shipped in that form
    (no /architect/final route). Shipped design = tool-loop behind AGENT_BACKEND (ADR-0007). → add superseded banner.
36. **docs/project_guide_rag.md** written as future plan; Phases A-C shipped (PROJECT_GUIDE_ENABLED live,
    architect.py:40). No `guide=true` payload exists — guide is the /architect endpoint. → status header + interface fix.
37. **docs/ingestion_pipelines.md:96-101** rollout names scripts that don't exist (batch_ingest_docs.py,
    stream_worker.py) while the real shipped CLI (ingest_docs.py) isn't acknowledged as the batch path.
38. **docs/MODERNIZATION_PLAN.md** PR table (0,A-I) has no status marks despite defining the ✅/🚧/🧩 legend and
    claiming to be the source of truth; every row has shipped per CHANGELOG. Narrative line 39 still future-tense
    ("we implement"). → add status column, all ✅.
39. **docs/capabilities_roadmap.md** item 9 "Evaluation and feedback" P0 (offline eval harness, golden sets, CI eval
    gates) — substantially shipped via LangSmith stack; LangSmith listed only as an "option" for tracing (line 76).

## Tier 6 — gaps in living docs

40. **docs/rag.md:32-48** RAG_EXCLUDE_FILES undocumented anywhere in docs/ (live at all three paths:
    doc_retriever.py:31, vector_retriever.py:98 with 2x over-fetch, ingest_docs.py:53). Also: `make ingest`
    unmentioned; expansion flags only reported on keyword path (doc_retriever.py:218-224).
41. **docs/agents.md:17-21** tool-budget behavior pre-dates the 2026-07-04 fix: no mention of the finalize-now
    instruction at the cap (langgraph_architect.py:72-84) or the empty-plan raise → builtin fallback (178-186).
42. **docs/agents.md:8-21** no pointer to the measured grid verdict (langgraph wins groundedness AND latency) —
    readers assume default = recommended. Link docs/eval_results/2026-07-04-grid-backend-tokens.md.
43. **docs/memory.md** doesn't say /architect integrates memory the same way, nor that the langgraph backend
    currently bypasses memory entirely (counters hardwired 0 — langgraph_architect.py:204-211).
44. **docs/api.md + capabilities_current.md** `/think` endpoint (app/routers/think.py:18) missing from both
    endpoint lists.
45. **docs/audit.md / observability docs** new audit fields undocumented: agent_backend, agent_tool_calls,
    llm_cost_usd. Zero LangSmith mention in observability.md despite tracing + eval integration shipped.
46. **docs/live_eval.md** no superseded-pointer to the LangSmith pipeline (it's now the legacy path).
47. **docs/llm_agent_streaming_prompts.md** no header noting it's superseded by eval_prompt_set_v2 for evals and
    deliberately RAG-excluded (it's still linked from README Contributing as starter prompts — fine, but say so).
48. **docs/README.md (index)** none of the six eval docs are listed.
49. **docs/testing.md** conftest stub-provider fixture unmentioned (tests are now offline-safe by design — worth a line).

## Verified accurate (spot-checked, no action)

CHANGELOG fully current through the eval work · README badges match CI gate · MCP entry point + tool names ·
pii.md (presidio) current · memory.md defaults all match code · agents.md defaults/cap/audit fields correct ·
eval doc image links resolve · prompt jsonl = 26 · ADR-0003 "Proposed" consistent with no feature-store code ·
openapi drift covered by CI check.

## Suggested PR shape

- **PR: docs-refresh (this review's output).** Tier 1 + 4 + 6 edits, Tier 5 superseded banners.
- **PR or same: env-example-refresh.** Tier 2 deletions + Tier 3 additions (touches only .env.example + config.md).
- Dead-flag deletions (10-12) are code-adjacent decisions: delete the lines vs implement the flags — flag to Rodrigo,
  default = delete.
