# DX Makefile for ai-architect.
# Targets are self-documenting: a `## ...` comment after a target shows up in
# `make help`, and `##@ ...` lines are group headers. Run `make` or `make help`.
.PHONY: help venv install test lint serve ingest sweep freeze export-openapi \
        eval eval-smoke eval-dataset eval-grid eval-live \
        dev-up dev-down prod-up prod-down logs test-docker

.DEFAULT_GOAL := help

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage: make \033[36m<target>\033[0m\n"} \
		/^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ Setup
venv: ## Create .venv (Python 3.11) and install the package editable
	@command -v python3.11 >/dev/null 2>&1 || { echo "python3.11 is required but not installed. Please install Python 3.11 (e.g., via pyenv or your package manager)." >&2; exit 1; }
	python3.11 -m venv .venv
	. .venv/bin/activate && pip install -U pip setuptools wheel
	. .venv/bin/activate && pip install -e .

install: ## Reinstall the package into an existing .venv
	. .venv/bin/activate && pip install -e .

##@ Test & Lint
test: ## Run the full offline test suite (stub LLM, no billed calls)
	. .venv/bin/activate && pytest -q

lint: ## Ruff check (auto-installs ruff if missing)
	. .venv/bin/activate && ruff --version >/dev/null 2>&1 || pip install ruff
	. .venv/bin/activate && ruff check . || true

##@ Run
serve: ## Run the uvicorn dev server on :8000 (auto-reload)
	. .venv/bin/activate && uvicorn app.main:app --reload

##@ Data
ingest: ## Build the Chroma vector store from DOCS_PATH (needed for RAG_BACKEND=vector)
	. .venv/bin/activate && python scripts/ingest_docs.py

sweep: ## Run the audit-store retention sweep
	. .venv/bin/activate && python scripts/sweep_retention.py

freeze: ## Freeze the current venv into requirements.txt
	. .venv/bin/activate && pip freeze > requirements.txt

export-openapi: ## Write the OpenAPI schema to disk
	. .venv/bin/activate && python scripts/export_openapi.py

##@ Eval  (BILLED OpenAI + LangSmith calls — never run casually; eval-smoke is free)
PREFIX ?= architect-eval
LIMIT ?= 0

eval: ## LangSmith eval on the golden dataset (vars: PREFIX, LIMIT, NOJUDGES=1)
	. .venv/bin/activate && python scripts/run_langsmith_eval.py --experiment-prefix $(PREFIX) --limit $(LIMIT) $(if $(NOJUDGES),--no-judges,)

eval-smoke: ## Fast free smoke: 3 examples, code evaluators only
	. .venv/bin/activate && python scripts/run_langsmith_eval.py --experiment-prefix smoke --limit 3 --no-judges

eval-dataset: ## Sync the golden dataset to LangSmith (DRYRUN=1 to preview)
	. .venv/bin/activate && python scripts/build_langsmith_dataset.py $(if $(DRYRUN),--dry-run,)

eval-grid: ## Run the backend/token experiment grid (CELLS="langgraph-2048 ...")
	. .venv/bin/activate && python scripts/run_experiment_grid.py $(if $(CELLS),--cells $(CELLS),)

# Legacy deterministic live-eval harness (kept for offline shape checks).
EVAL_FILE ?= eval/architect_prompts.jsonl
EVAL_LIMIT ?= 0
SUMMARY_MIN ?= 40
STEPS_MIN ?= 2
STEP_CHARS ?= 20
LLM_MODEL ?=

eval-live: ## Legacy offline live-eval (deterministic shape checks; vars: EVAL_FILE, EVAL_LIMIT)
	. .venv/bin/activate || true; python scripts/run_live_eval.py --file $(EVAL_FILE) --limit $(EVAL_LIMIT) --summary-min $(SUMMARY_MIN) --steps-min $(STEPS_MIN) --step-chars $(STEP_CHARS) $(if $(LLM_MODEL),--llm-model $(LLM_MODEL),)

##@ Docker  (dev-up = base + docker-compose.override.yml; prod-up = base only)
dev-up: ## Start the stack with the dev override merged
	docker compose up --build -d

dev-down: ## Stop the dev stack
	docker compose down

prod-up: ## Start the stack from docker-compose.yml only (no override)
	docker compose -f docker-compose.yml up --build -d

prod-down: ## Stop the base-only stack
	docker compose -f docker-compose.yml down

logs: ## Tail the compose logs (last 200 lines, follow)
	docker compose logs -f --tail=200

test-docker: ## Run the test suite inside the api container
	docker compose run --rm api /bin/sh -lc ". /opt/venv/bin/activate || true; [ -d /opt/venv ] || python -m venv /opt/venv; . /opt/venv/bin/activate; pip install -e .; pytest -q"
