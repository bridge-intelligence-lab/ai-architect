---
title: "MLOps Plan: Risk Scoring Model, Drift Monitoring, and Registry"
status: historical
module: ml
last_reviewed: 2026-07-04
---

# MLOps Plan: Risk Scoring Model, Drift Monitoring, and Registry

## Purpose

- Add real MLOps value to the project with a versioned ML model for risk scoring, clear data vs. model drift monitoring, and safe promotion/rollback.
- Keep heuristic scoring as reliable baseline; use ML to enrich and triage, not to degrade quality.

## Scope (Phased, value-first)

- Phase 1 — Model + Registry + Serving + Audit (recommended now)
  - Train a small sklearn Pipeline (TF-IDF + LogisticRegression).
  - Log run to MLflow with params/metrics/artifacts; optionally register in Model Registry.
  - Serve the model when RISK_ML_ENABLED=true; include audit fields: risk_score_method="ml", risk_model_version, risk_threshold.
  - Fallback to heuristic if model is missing.
- Phase 2 — Data Drift (PSI) Monitoring (recommended now)
  - Extract lightweight drift features per request (e.g., text_length, risky_token_count, top-N term freqs).
  - Run scheduled drift sweep comparing recent features vs. baseline using PSI (ml/drift.py).
  - Log PSI to MLflow and expose summary; threshold guidance: <0.1 stable, 0.1–0.25 monitor, >0.25 alert.
- Phase 3 — Model Drift (Performance) Monitoring
  - With labels: evaluate precision/recall/F1 on sampled labeled recent data; log to MLflow.
  - Without labels: use proxies (LLM escalation rate, label distribution shifts, operator feedback).
  - Trigger retraining candidates if metrics degrade beyond thresholds.
- Phase 4 — Controlled Retraining and Promotion
  - Scheduled retraining; compare against current Production model.
  - Register new model to Staging if it outperforms; manual or gated automatic promotion to Production.
  - Optional canary rollout; keep rollback path via MLflow model version pinning.

## Model Definition

- Task: classify incident text into risk levels with a calibrated score.
- Data schema: {id, text, label in {low, medium, high}, tags[], created_at}.
- Features: start with TF-IDF; optionally add embeddings or a small transformer later.
- Baseline model: LogisticRegression on TF-IDF; pipeline serialized with joblib or managed by MLflow.
- Outputs: risk_score in [0,1], risk_label (thresholded), optional categories/explanations.

## Serving Integration

- Loader: use app/services/mlflow_client.py (already present) or a simple joblib loader.
- Switch: RISK_ML_ENABLED=true enables ML path; otherwise heuristic.
- Audit fields added by /risk when ML is active:
  - risk_score_method: "ml"
  - risk_model_version: MLflow run_id or registry version
  - risk_threshold: current threshold used

## Data Drift vs. Model Drift

- Data drift: input distribution shifts (new terminology, length changes). Detect via PSI between baseline and recent features.
- Model drift: performance degradation (precision/recall/F1) due to data changes or concept shift. Detect via evaluation on labeled samples or proxy metrics.
- Actions:
  - Data drift alert: collect samples for labeling; monitor performance.
  - Model drift alert: retrain; evaluate; promote if better.

## Planned Components (code)

- Training: ml/train.py (exists) — extend to log to MLflow and save baseline feature stats.
- Drift sweep: scripts/sweep_drift.py (exists) — or add scripts/sweep_data_drift.py to compute PSI from recent requests.
- Evaluation: scripts/evaluate_model.py (new) for labeled eval and comparison.
- Serving: app/services/risk_scorer.py — use ML model when enabled; add audit fields.
- Metrics: expose risk_requests_total{method}, risk_score_value histogram, last_data_drift_psi_* gauges.

## Testing Strategy

- Data drift:
  - Unit test PSI on identical vs. shifted distributions (tests/test_psi.py exists).
  - Add tests for drift feature extraction and sweep decision thresholds.
- Model drift:
  - Use a tiny labeled fixture and stub models to verify metrics and degradation detection without heavy deps.
- Serving:
  - Test that with ML enabled, /risk returns method="ml", includes model version, and score bounds.

## Docs and Demos

- docs/mlops_plan.md (this document) — overview, phases, and guidance.
- docs/ml.md — training, evaluation, registry, serving steps (to be added/expanded).
- docs/drift.md — simple explanation of data vs. model drift, PSI, thresholds, and how to run sweeps (to be added).
- Manual E2E: optional steps to train/register a tiny model and enable ML to see audit fields populated.

## Current Status (2025-10-05)

- Heuristic scorer and /risk endpoint are live.
- Deterministic pseudo-ML path exists but is disabled for launch to prioritize Architect + UI.
- PSI implementation exists (ml/drift.py) and is tested.
- Next up post-launch: implement Phase 1 and 2 in code, wire audit fields, and add drift docs.

## Notes

- Keep ML optional and non-blocking; default to heuristic.
- Optimize for deterministic, cheap, and observable behavior first; add LLM escalation as needed.
