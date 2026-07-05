# AI Architect Launch Plan (Live Document)

Status: in-progress (commits to main)
Owner: you (solo dev)
Scope: Architect-first OSS launch with engaging chat UI, structured agent, and streaming.

## Vision and Goals

- Rebrand from ai-risk-monitor posture to an Architect-first experience ("AI Architect").
- Single primary experience: Architect agent that designs setup plans, suggests flags, and grounds on docs when allowed.
- Engaging chat UX with progressive streaming and clear observability.
- Lightweight feature request flow via prefilled GitHub issues.

## Cut-off for Today (Must Have)

- Architect-first focus in README and UI; deeper details moved to docs/.
- Structured Architect Agent with dynamic grounding.
- SSE streaming endpoint for Architect and a chat UI that consumes it.
- Friendly agent tone, grounded badge, and feature request CTA (prefilled GitHub issue link).
- README hero image and branding updates aligned with docs/.

## Backend Changes

- ArchitectPlan (pydantic)
  - + suggest_feature: bool = False
  - + feature_request: str | None = None
  - + tone_hint: str | None = None
- Architect Agent
  - Retrieval first; grounded_used=true when citations present.
  - Light heuristic to propose suggest_feature + feature_request when a gap is implied.
- Architect Router
  - POST /architect unchanged for compatibility.
  - No explicit mode; grounded decided dynamically (heuristic) when not provided.
  - New GET /architect/stream (SSE) emits events: meta, summary, steps, flags, citations, feature, audit.

## UI Changes (ChatGPT-style)

- Two-pane layout:
  - Left: chat (agent/user bubbles, initial agent greeting, input dock at bottom).
  - Right: stats & debug (grounded chip, citation count, tokens/cost, audit JSON collapsible, RAG flags).
- Streaming: EventSource to /architect/stream; render chunks progressively.
- Feature CTA: Create GitHub Issue (prefilled) and Copy Template button. Feature proposals can originate from the Architect agent when gaps are detected; encourage users to submit issues and PRs.
- No mode selector; no grounded toggle.

## Streaming (SSE) Contract

- Endpoint: GET /architect/stream?question=...&session_id=&user_id=
- Events and payloads (JSON):
  - event: meta → { provider, model, grounded_used }
  - event: summary → "text"
  - event: steps → ["...", "..."]
  - event: flags → ["...", "..."]
  - event: citations → [{ source, page?, snippet? }, ...]
  - event: feature → "feature_request text"
  - event: audit → full audit dict

## GitHub Issue CTA (MVP)

- Repo: bridge-intelligence-lab/ai-architect (or update to this repo if preferred)
- Link template: https://github.com/bridge-intelligence-lab/ai-architect/issues/new?title=<encoded>&body=<encoded>
- Include summary, steps, flags, and user question in body.
- OAuth/device flow deferred post-launch.

## Branding and README

- Title: AI Architect
- Hero image at top (docs/images/hero.png)
- Root README is high-level; detailed topics live under docs/ and are linked prominently.

## Post-launch Backlog (Nice to Have)

- True server-side conversational memory for Architect (short summary of prior turns to agent).
- Token-level/step-level streaming; partial LLM chunks.
- GitHub OAuth and backend issue creation with assignment.
- Deeper RAG scoring and thresholding for grounded_used.
- Router UI and docs revisited.
- Full repo rename and package-level refactor if desired.

## Checklist (Today)

- [x] Architect router uses structured agent; remove brittle JSON parsing
- [x] Dynamic grounding; drop explicit modes
- [x] Extend plan schema (suggest_feature, feature_request, tone_hint)
- [x] SSE endpoint implemented and wired
- [x] Architect UI chat (left pane) + stats (right pane)
- [x] Streaming UI logic (EventSource)
- [x] README: hero image + branding updates
- [ ] Feature CTA with prefilled GitHub issue link

## Notes

- Keep tests green by leaving POST /architect behavior/stability intact.
- Avoid heavy refactors today; focus on UX, streaming, and messaging polish.
