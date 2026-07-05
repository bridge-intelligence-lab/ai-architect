---
title: PII detection and configuration
status: current
module: governance
last_reviewed: 2026-07-04
source:
  - app/services/pii_detector.py
  - app/services/pii_presidio.py
---

# PII detection and configuration

Two detection backends, selected by `PII_BACKEND`:

- **`regex` (default).** Simple, deterministic detector based on regex and
  heuristics. Masked previews, counts, and detected types, no external
  calls; this is what tests and CI exercise.
- **`presidio`.** Microsoft Presidio's AnalyzerEngine (NER + pattern
  recognizers) in `app/services/pii_presidio.py`, same result shape plus a
  per-entity `score`. Optional install: `pip install .[presidio]` and a
  spaCy model (`python -m spacy download en_core_web_sm`; override with
  `PII_SPACY_MODEL`). Confidence cutoff via `PII_PRESIDIO_THRESHOLD`
  (default 0.5). If Presidio is missing or fails, detection falls back to
  the regex baseline; results report `pii_backend` = backend actually used.

Environment variables
- PII_BACKEND: regex (default) | presidio
- PII_PRESIDIO_THRESHOLD: minimum Presidio confidence score (default 0.5)
- PII_SPACY_MODEL: spaCy model for the Presidio NLP engine (default en_core_web_sm)
- PII_TYPES: comma-separated base types to enable. Default: email,phone,ssn,credit_card,ipv4
  - Additional base types available: ipv6, iban, passport
- PII_LOCALES: comma-separated locales to enable locale-specific patterns (e.g., US,UK,CA,DE); regex backend only

Request-level filtering
- The /pii endpoint accepts an optional types array in the request body to override enabled base types for that request only (e.g., ["ssn"]). Locales remain configured via PII_LOCALES.

Base patterns
- email: standard username@domain.tld format
- phone: E.164-like and common national formats, supporting separators and parentheses
- ssn: US Social Security Number (NNN-NN-NNNN)
- ipv4 / ipv6: IPv4 and simplified IPv6
- iban: simplified IBAN (country code + alphanumeric body; no checksum validation)
- passport: generic 7–9 alphanumeric (heuristic)
- credit_card: 13–19 digits with spaces/dashes; validated with Luhn

Locale-specific patterns (simplified)
- US
  - postal_us: ZIP or ZIP+4 (NNNNN or NNNNN-NNNN)
  - dl_us: generic 7–9 alphanumeric placeholder (varies by state in reality)
- UK
  - postal_uk: UK postcode (broad simplified)
  - ni_uk: National Insurance number (AA999999A, with allowed letter ranges)
- CA
  - sin_ca: Canadian SIN (very simplified; 9 digits with optional separators)
  - postal_ca: Canadian postal code (A1A 1A1 pattern)
- DE
  - postal_de: 5-digit postal code
  - id_de: generic 9–10 alphanumeric placeholder

Masking behavior
- Detected values are masked with head and tail visible by default (2 chars each). Example:
  - alice@example.com → al******************om
  - 4111 1111 1111 1111 → 41**************11

Performance and determinism
- Patterns are compiled per request to respect dynamic environment changes and keep tests deterministic.
- Input text is capped to 5000 characters to avoid pathological regex costs.

False positives and tuning
- Some locale and generic patterns are simplified and may yield false positives; adjust PII_TYPES/PII_LOCALES accordingly.
- Consider narrowing keywords or adding word boundaries if you extend patterns.

Examples
```
export PII_TYPES="email,phone,ssn,credit_card,ipv4"
export PII_LOCALES="US,UK,CA"
curl -X POST localhost:8000/pii \
  -H "Content-Type: application/json" \
  -H "X-User-Role: analyst" \
  -d '{"text":"Contact bob@example.com, UK NI AB123456C, ZIP 12345-6789"}'
```
