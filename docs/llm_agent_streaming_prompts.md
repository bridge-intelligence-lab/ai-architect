---
title: LLM Agent Streaming Test Prompts
status: historical
module: community
last_reviewed: 2026-07-04
---

# LLM Agent Streaming Test Prompts

> **Scope note.** These prompts are for exercising the streaming UI by hand.
> For evaluation they are superseded by `docs/eval_prompt_set_v2.md` /
> `eval/architect_prompts_v2.jsonl` (the LangSmith golden dataset). This file
> is deliberately excluded from the RAG corpus via `RAG_EXCLUDE_FILES` — it
> contains the eval questions verbatim and would otherwise be retrieved as
> "context" for them.

Use these prompts to exercise different parts of the system and the streaming UI. They are grouped by scenario. Paste them into the Architect UI or call the streaming endpoint.

Streaming endpoint
- GET /architect/stream?question=...

---

## Grounded, architecture-focused (should yield citations, steps, flags)
1) Explain how to enable Architect mode and what env flags are involved. Include defaults and any RAG flags.
2) Outline the steps to integrate the Router with RAG and Policy Navigator. What files should I modify?
3) Where are audit rows written and which fields are tracked? How do I configure retention and metrics?
4) How do I protect /metrics in production and configure Prometheus and Grafana to scrape it?
5) What RBAC roles are enforced for /query, /predict, and memory endpoints? Provide examples.

## Brainstorm/design (ungrounded or dynamic grounding)
6) Propose a plan to add a "policy mapping" feature connecting docs to endpoints. Include UI and flags.
7) I want to add a new endpoint for sentiment classification. Outline files, tests, and deployment steps.
8) Recommend a strategy to migrate from stub LLM to a hosted provider with token/cost tracking.

## Debugging and behavior checks
9) When does grounded_used become true in Architect responses, and how are citations collected?
10) If the LLM output is malformed, what deterministic fallbacks will fill summary, steps, and flags?
11) What are the key env variables affecting RAG behavior (multi-query, hyDE), and how do they change the plan?

## Memory/session
12) How can I persist session turns across page reloads, and where is session_id used?

## Feature CTA prompt
13) Suggest a feature to automatically create a GitHub issue from the Architect plan. Provide a title and body suitable for an issue.

Notes
- These should trigger a good mix of meta, summary typing, steps, flags, citations, and the final audit in the streaming UI.
