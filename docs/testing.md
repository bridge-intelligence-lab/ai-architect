# Testing Cheat Sheet

## One-time setup (local)
python -m venv .venv
. .venv/bin/activate
pip install -e .

### CPU-only local install tip
If installing locally pulls a GPU-enabled PyTorch wheel via sentence-transformers, preinstall CPU PyTorch wheels first, then install the project:

pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio
pip install -e .

## Full test suite
.venv/bin/python -m pytest -q

## Verbose output and show logs
.venv/bin/python -m pytest -vv -s

## Run a single file / test
.venv/bin/python -m pytest -q tests/test_predict.py
.venv/bin/python -m pytest -q tests/test_predict.py::test_predict_after_train

## Re-run only failed tests
.venv/bin/python -m pytest --lf

## Stop at first failure
.venv/bin/python -m pytest -x

## Show slow tests
.venv/bin/python -m pytest --durations=10

## With environment variables
MLFLOW_TRACKING_URI=.mlruns MLFLOW_EXPERIMENT_NAME=ai-architect-test \
  .venv/bin/python -m pytest -q

METRICS_TOKEN=secret \
  .venv/bin/python -m pytest -q tests/test_rbac.py::test_metrics_protected_with_token

## Keyword expression
.venv/bin/python -m pytest -k "rag and idempotent"

## Coverage (enforced in CI)
CI runs the suite with a hard coverage gate: line coverage of `app/` and
`scripts/` must be at least **75%** or the build fails
(`pytest -q --cov=app --cov=scripts --cov-fail-under=75`, see
`.github/workflows/ci.yml`). To reproduce locally:

pip install pytest-cov
.venv/bin/python -m pytest --cov=app --cov=scripts --cov-report=term-missing --cov-fail-under=75

## Offline by default
`tests/conftest.py` pins the stub LLM provider (and related env) for every
test, so a populated local `.env` cannot leak a real provider key into the
suite. Test runs make no billed API calls; keep new tests deterministic and
offline.

## Quality evaluation (separate from unit tests)
Answer-quality regression is handled by the LangSmith eval pipeline (golden
dataset + code evaluators + calibrated LLM judges), not pytest. See
`docs/langsmith_test_plan.md` and `docs/eval_results/`.

## Lint/format (optional)
pip install ruff
.venv/bin/ruff check .
.venv/bin/ruff format .

## Type check (optional)
pip install mypy
.venv/bin/mypy app
