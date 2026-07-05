---
title: Router configuration
status: current
module: router
last_reviewed: 2026-07-04
source:
  - app/services/router.py
---

# Router configuration

The Router selects an intent for /query: qa, pii_detect, risk_score, policy_navigator, pii_remediation, or other.

## Enable the router

- export ROUTER_ENABLED=true

## Select backend (default is rules)

- export ROUTER_BACKEND=rules

## Provide rules inline via JSON

- export ROUTER_RULES_JSON='{"rules":[{"intent":"pii_detect","keywords_any":["ssn","pii"],"priority":100},{"intent":"qa","keywords_any":["policy"],"priority":10}],"default_intent":"qa"}'

## Or load rules from a file

- echo '{"rules":[{"intent":"risk_score","keywords_any":["risk","severity"],"priority":50}],"default_intent":"qa"}' > router_rules.json
- export ROUTER_RULES_PATH=$PWD/router_rules.json

## Behavior

- Priority determines which rule wins if multiple match.
- If no rules are configured or no rule matches, builtin heuristics apply (e.g., email/ssn/credit card → pii_detect; risk/severity → risk_score; policy/gdpr/hipaa/compliance → policy_navigator; otherwise qa).
- If grounded=true, the router returns qa (RBAC still applies for grounded queries).

## Intent names and aliases

- Canonical intent names: qa, pii_detect, risk_score, policy_navigator, pii_remediation, other.
- Alias: some tests/docs may use the shorthand policy_nav; the router emits policy_navigator in audit.router_intent.
- When ROUTER_ENABLED=false, the builtin heuristics run and audit.router_backend is set to "simple".

## Try it

- curl -X POST localhost:8000/query -H 'Content-Type: application/json' -d '{"question":"Email is bob@example.com","grounded": false}'
- Expected: audit.router_intent == "pii_detect"

See docs/router_rules.md for the rules schema and more examples.

## Design

**Owns:** intent selection for /query: mapping a question (plus groundedness) to one
of the canonical intents. `route_intent(question, grounded)` in
`app/services/router.py` is the whole public surface.

**Contract:** returns exactly one intent string (qa, pii_detect, risk_score,
policy_navigator, pii_remediation, other); never raises; the audit records
`router_backend` (rules | builtin | simple) and `router_intent`.

**Invariants:**
- Resolution order: configured rules (highest priority wins) first; when rules
  yield the default intent but the builtin heuristics find a stronger one (e.g.
  pii), the builtin result wins. No rules configured = builtin heuristics.
- `grounded=true` always routes to qa: a user explicitly asking for citations has
  declared their intent, so keyword heuristics must not override it.
- Rules are loaded once and cached per process (`ROUTER_RULES_JSON` beats
  `ROUTER_RULES_PATH`).

**Why it exists:** one place to decide "what kind of request is this," so endpoint
behavior and audit stay consistent as intents grow. It is deliberately cheap
(keyword rules, no LLM call) because it runs on every /query.

**Non-goals:** no build/collaborate intent yet (the feature-CTA heuristic in the
architect wrapper covers that need today; folding it into the router is the planned
path for intent-conditioned responses), no LLM-based classification.
