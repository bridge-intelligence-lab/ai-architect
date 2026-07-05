# Approach: LangGraph backend parity (session memory + feature CTA) and SSE UX

Status: IMPLEMENTED 2026-07-04 (PR #27). All four changes A-D landed, plus
RAG_EXCLUDE_DIRS pulled forward from backlog step 4 (worklog files entered docs/ in
this PR, so the exclusion had to ship with them) and fresh per-example session ids in
both eval harnesses (with shared "default" sessions, backend memory would leak context
across eval questions). Full suite 179 passed; verified live over SSE. Note for the
next grid run: the earlier builtin-vs-langgraph latency comparison was unfair, since
langgraph skipped memory reads entirely.
Relates to: 2026-07-04-docs-knowledge-backlog.md items 1 and 2

## Findings (investigated 2026-07-04)

Both reported bugs share one root cause: `AGENT_BACKEND=langgraph` became the default
in .env after the eval grid showed it winning, but the langgraph backend lacks feature
parity with builtin. Nothing "broke"; the backend switch exposed gaps.

1. Session memory: `run_architect_agent` delegates to `run_langgraph_architect` before
   any memory code runs (architect_agent.py:50-56). The langgraph path accepts
   `session_id` but never calls `load_turns`/`load_summary`/`save_turn` and hardcodes
   memory audit stats to 0 (langgraph_architect.py:205-211). Memory only works on the
   builtin path. Verified live: `/architect/stream` returns `memory_short_reads: 0`
   with memory flags on; memory_short.db has no rows for real UI session ids.

2. GitHub-issue CTA: the UI shows it only on an SSE `feature` event, which fires only
   when the plan has `suggest_feature` set. Only the builtin agent sets it
   (architect_agent.py:236). The langgraph backend never does, so the CTA never renders.

3. SSE: server side works (verified with curl: meta/summary/steps/flags/citations/audit
   all arrive). But the endpoint runs the full agent BEFORE emitting any event
   (architect_stream.py:64), so the UI sees nothing for the entire agent runtime, then
   everything at once. With langgraph latency this reads as "SSE broken."

## Proposed changes

A. Hoist short-memory read/write out of the builtin agent into the backend-agnostic
   wrapper (`run_architect_agent`): load turns/summary before dispatch, pass context to
   whichever backend runs, save user+assistant turns after. Both backends get memory;
   audit stats become real for langgraph. Builtin keeps its current behavior.

B. Port `suggest_feature` intent detection the same way (wrapper-level, post-backend),
   so the feature CTA is backend-independent.

C. SSE minimal fix: emit an immediate `status` event ("planning...") before invoking
   the agent, then the existing events when ready. True token streaming is out of scope
   (would require streaming the LangGraph run; separate item if wanted).

D. Tests: unit test that langgraph path persists and reads turns (stub LLM); golden
   prompts for the build/collaborate intent asserting `suggest_feature`; keep both in
   the regression suite so backend switches can't silently drop capabilities again.

## Eval impact

Memory context changes langgraph inputs slightly (prepended conversation context on
multi-turn sessions only; single-turn eval prompts unaffected). suggest_feature is
additive. Run the baseline before merging (backlog step 3) and diff after.

## Out of scope

Long-term memory parity for langgraph (MEMORY_LONG) beyond stats plumbing; token-level
streaming; intent-flexible response shapes (backlog step 6).
