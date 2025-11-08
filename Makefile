# Simple DX Makefile for ai-architect
.PHONY: help venv install test serve lint ingest sweep freeze export-openapi dev-up dev-down prod-up prod-down logs

help:
	@echo "Targets: venv, install, test, serve, lint, ingest, sweep, freeze, export-openapi, dev-up, dev-down, prod-up, prod-down, logs"

venv:
	@command -v python3.11 >/dev/null 2>&1 || { echo "python3.11 is required but not installed. Please install Python 3.11 (e.g., via pyenv or your package manager)." >&2; exit 1; }
	python3.11 -m venv .venv
	. .venv/bin/activate && pip install -U pip setuptools wheel
	. .venv/bin/activate && pip install -e .

install:
	. .venv/bin/activate && pip install -e .

test:
	. .venv/bin/activate && pytest -q

serve:
	. .venv/bin/activate && uvicorn app.main:app --reload

lint:
	. .venv/bin/activate && ruff --version >/dev/null 2>&1 || pip install ruff
	. .venv/bin/activate && ruff check . || true

ingest:
	. .venv/bin/activate && python scripts/ingest_docs.py

sweep:
	. .venv/bin/activate && python scripts/sweep_retention.py

freeze:
	. .venv/bin/activate && pip freeze > requirements.txt

export-openapi:
	. .venv/bin/activate && python scripts/export_openapi.py

# Docker helpers

dev-up:
	docker compose up --build -d

dev-down:
	docker compose down

prod-up:
	docker compose -f docker-compose.yml up --build -d

prod-down:
	docker compose -f docker-compose.yml down

logs:
	docker compose logs -f --tail=200

test-docker:
	docker compose run --rm api /bin/sh -lc ". /opt/venv/bin/activate || true; [ -d /opt/venv ] || python -m venv /opt/venv; . /opt/venv/bin/activate; pip install -e .; pytest -q"

# Live eval
EVAL_FILE ?= eval/architect_prompts.jsonl
EVAL_LIMIT ?= 0
SUMMARY_MIN ?= 40
STEPS_MIN ?= 2
STEP_CHARS ?= 20

LLM_MODEL ?=

eval-live:
	. .venv/bin/activate || true; python scripts/run_live_eval.py --file $(EVAL_FILE) --limit $(EVAL_LIMIT) --summary-min $(SUMMARY_MIN) --steps-min $(STEPS_MIN) --step-chars $(STEP_CHARS) $(if $(LLM_MODEL),--llm-model $(LLM_MODEL),)
