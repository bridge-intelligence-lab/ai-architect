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

Enable the router
- export ROUTER_ENABLED=true

Select backend (default is rules)
- export ROUTER_BACKEND=rules

Provide rules inline via JSON
- export ROUTER_RULES_JSON='{"rules":[{"intent":"pii_detect","keywords_any":["ssn","pii"],"priority":100},{"intent":"qa","keywords_any":["policy"],"priority":10}],"default_intent":"qa"}'

Or load rules from a file
- echo '{"rules":[{"intent":"risk_score","keywords_any":["risk","severity"],"priority":50}],"default_intent":"qa"}' > router_rules.json
- export ROUTER_RULES_PATH=$PWD/router_rules.json

Behavior
- Priority determines which rule wins if multiple match.
- If no rules are configured or no rule matches, builtin heuristics apply (e.g., email/ssn/credit card → pii_detect; risk/severity → risk_score; policy/gdpr/hipaa/compliance → policy_navigator; otherwise qa).
- If grounded=true, the router returns qa (RBAC still applies for grounded queries).

Intent names and aliases
- Canonical intent names: qa, pii_detect, risk_score, policy_navigator, pii_remediation, other.
- Alias: some tests/docs may use the shorthand policy_nav; the router emits policy_navigator in audit.router_intent.
- When ROUTER_ENABLED=false, the builtin heuristics run and audit.router_backend is set to "simple".

Try it
- curl -X POST localhost:8000/query -H 'Content-Type: application/json' -d '{"question":"Email is bob@example.com","grounded": false}'
- Expected: audit.router_intent == "pii_detect"

See docs/router_rules.md for the rules schema and more examples.
