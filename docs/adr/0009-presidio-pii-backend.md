---
title: "ADR 0009: Presidio PII backend behind PII_BACKEND; regex baseline kept"
status: current
module: architecture
last_reviewed: 2026-07-05
decision_date: 2026-07-04
adr_status: Accepted
---

# ADR 0009: Presidio PII backend behind PII_BACKEND; regex baseline kept

## Context

- The PII detector is hand-rolled regex/heuristics: deterministic, offline,
  and fine as a baseline, but pattern-only detection misses contextual
  entities (names, locations) and produces locale false positives.
  ADR-0004's build-vs-buy matrix marked this as a place where a library
  wins on its own claim: Presidio combines NER with curated pattern
  recognizers and confidence scores.
- Presidio pulls spaCy plus a language model, which is far too heavy to
  force on every install or on CI.

## Decision

- Add `app/services/pii_presidio.py` behind `PII_BACKEND=presidio`; the
  regex baseline stays the default and the fallback whenever Presidio is
  unavailable or errors (missing package, missing spaCy model, runtime
  failure). Results report `pii_backend` = backend actually used.
- Presidio is an optional dependency extra (`pip install .[presidio]`),
  keeping core installs and CI light. The spaCy model is configurable via
  `PII_SPACY_MODEL` (default en_core_web_sm); confidence cutoff via
  `PII_PRESIDIO_THRESHOLD` (default 0.5).
- Both backends return the same shape (entities with type, masked
  value_preview, span; counts; types_present; total); Presidio entities add
  `score`. Type filters translate to Presidio entity names
  (email→EMAIL_ADDRESS, ...), so `/pii` request-level filtering works
  unchanged.

## Consequences

- Production deployments can opt into NER-grade detection without any test
  or CI dependency on model downloads: tests exercise the mapping,
  threshold, and type translation through a scripted fake Presidio, and
  the fallback path is tested by blocking the import.
- Locale-specific regex patterns (PII_LOCALES) remain regex-backend-only;
  Presidio has its own recognizer registry, and extending it is follow-up
  work if needed.
