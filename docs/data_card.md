---
title: Data Card
status: current
module: ml
last_reviewed: 2026-07-04
source:
  - ml/
---

# Data Card

## Overview
- Dataset name: (e.g., Synthetic classification dataset)
- Purpose: Train a simple classification model for demo purposes
- Owner: Rodrigo
- Date: 2025-10-04

## Sources & Collection
- Source: Synthetic via sklearn.make_classification
- Collection method: Generated locally in ml/train.py
- Licensing: N/A (synthetic)

## Schema
- Features: f0..f7 (float)
- Target: target (0/1)

## Preprocessing
- Train/test split: 75/25
- Normalization/Scaling: None (LogisticRegression handles raw features)
- Missing values: None (synthetic)

## Quality & Bias
- Balanced classes: roughly balanced
- Known biases: None (synthetic); in real data, consider demographic parity and representational bias

## Privacy & Compliance
- No PII; synthetic only
- Follow denylist and anonymization settings in the app for logs

## Limitations
- Synthetic data does not reflect real-world distributions
- Metrics are not indicative of production performance

## Maintenance
- Update cadence: on-demand
- Point of contact: <your.email@example.com>
