---
title: Model Card
status: current
module: ml
last_reviewed: 2026-07-04
---

# Model Card

## Overview

- Model: Logistic Regression (sklearn)
- Use case: Binary classification (demo)
- Owner: Rodrigo
- Date: 2025-10-04

## Intended Use

- Demo for MLflow logging and serving via /predict
- Not for production use

## Training Data

- Dataset: Synthetic via sklearn.make_classification (see Data Card)
- Features: f0..f7, Target: 0/1
- Train/test split: 75/25

## Metrics

- Reported in ml/train.py: accuracy, AUC (on test split)
- Example (from a recent run): accuracy ~0.81, AUC ~0.91

## Evaluation

- Quick hold-out test only; no cross-validation
- No fairness or robustness tests included

## Limitations & Risks

- Not calibrated; may be overconfident
- Synthetic data; no guarantees on real-world performance
- No bias analysis

## Ethical Considerations

- Avoid using this model in real decision-making
- For real deployments, include bias/fairness audits and governance

## Maintenance & Versioning

- Logged to MLflow with params/metrics/artifacts
- Model version tracked by run_id
- Retraining criteria: drift (PSI) or performance thresholds

## Contact

- <your.email@example.com>
