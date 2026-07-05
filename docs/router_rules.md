---
title: Router rules (v2)
status: current
module: router
last_reviewed: 2026-07-04
source:
  - app/services/router.py
---

# Router rules (v2)

The router decides which intent to execute: qa, pii_detect, risk_score, policy_navigator, pii_remediation, other.

By default, the router uses a rules backend (v2) that can be configured via JSON. If no rules are configured or no rule matches, builtin heuristics are used as a fallback so common cases (PII, risk) still work out of the box.

Environment variables
- ROUTER_ENABLED=true|false
- ROUTER_BACKEND=rules (default)
- ROUTER_RULES_JSON='{"rules": [...], "default_intent": "qa"}'
- ROUTER_RULES_PATH=/path/to/rules.json

Rules schema
- rules: array of rule objects
  - intent: one of [qa, pii_detect, risk_score, policy_navigator, pii_remediation, other]
  - keywords_any: array of lowercase substrings to match (case-insensitive)
  - priority: integer; higher wins
- default_intent: string; used when no rule matches (qa recommended)

Example (inline JSON)
```
{
  "rules": [
    {"intent": "pii_detect", "keywords_any": ["ssn", "pii", "credit card"], "priority": 100},
    {"intent": "risk_score", "keywords_any": ["risk", "severity"], "priority": 50},
    {"intent": "qa", "keywords_any": ["policy", "gdpr", "hipaa"], "priority": 10}
  ],
  "default_intent": "qa"
}
```

Loading from a file
```
echo '{
  "rules": [
    {"intent": "pii_detect", "keywords_any": ["ssn", "pii"], "priority": 100}
  ],
  "default_intent": "qa"
}' > router_rules.json
export ROUTER_RULES_PATH=$PWD/router_rules.json
```

Behavior notes
- Grounded queries (grounded=true) always route to qa; endpoint RBAC applies.
- Priority determines which rule wins when multiple rules match.
- If rules are not provided or no rule matches, builtin heuristics still run to preserve sensible defaults:
  - pii_detect if the question mentions email, ssn, social security, credit card, iban, ipv4/ipv6, passport, phone number
  - risk_score if the question mentions risk, severity, score, impact, hazard, danger
  - policy_navigator for policy/regulation/gdpr/hipaa/compliance
  - Otherwise qa

Intent names and aliases
- Canonical: qa, pii_detect, risk_score, policy_navigator, pii_remediation, other.
- Alias: some tests/docs may use the shorthand policy_nav; the router emits policy_navigator in audit.router_intent.
- When ROUTER_ENABLED=false, builtin heuristics are used and audit.router_backend is "simple".

Troubleshooting
- Matching is case-insensitive substring-based; include stems for broader matches (e.g., "anonymiz" catches anonymize/anonymization).
- Validate JSON: echo $ROUTER_RULES_JSON | python -m json.tool
- If audit.router_intent is qa unexpectedly:
  - Check grounded flag; grounded=true forces qa
  - Ensure rules are loaded (check ROUTER_RULES_JSON/PATH)
  - Remember builtin fallback may still choose qa if no strong signals are present

Security considerations
- The router only selects intent; it doesn’t bypass endpoint RBAC. Grounded QA still requires analyst/admin.
