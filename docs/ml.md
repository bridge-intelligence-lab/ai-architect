---
title: ML and Drift
status: current
module: ml
last_reviewed: 2026-07-04
source:
  - ml/
  - app/services/mlflow_client.py
---

# ML and Drift

## Training

- Script: ml/train.py
- MLflow env vars:
  - MLFLOW_TRACKING_URI
  - MLFLOW_EXPERIMENT_NAME
- Artifacts logged per run:
  - model (sklearn)
  - model signature (inferred via mlflow.models.signature.infer_signature)
  - feature_order.json (configurable via MLFLOW_FEATURE_ORDER_ARTIFACT): { feature_order: [ ... ] }
- Quick start (local):
  - . .venv/bin/activate
  - export MLFLOW_TRACKING_URI=.mlruns; export MLFLOW_EXPERIMENT_NAME=ai-architect
  - python ml/train.py
  - Then POST /predict with a features object containing exactly these columns.

## Drift (PSI)

- Script: ml/drift.py
- PSI implementation:
  - Shared bin edges between baseline and new arrays
  - Epsilon smoothing to avoid zero division
- Usage:
  - python ml/drift.py --baseline ml/data/baseline.csv --input ml/data/new_batch.csv --threshold 0.2
- Exit codes:
  - 0: no retrain recommended
  - 1: retrain recommended (PSI > threshold)

## Notes

- CPU-only installs by default:
  - Dockerfile installs sentence-transformers using the PyTorch CPU wheel index, which ensures CPU torch wheels are selected.
  - To switch to GPU later, modify Dockerfile to use a CUDA-specific index URL and matching torch/torchvision/torchaudio versions.
- Ensure numeric columns are aligned between baseline and input.
- Data/model cards: see docs/model_card.md and docs/data_card.md
