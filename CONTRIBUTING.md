# Contributing

Thanks for your interest in contributing! This project aims to be a minimal reference for safe, observable, and cost-aware AI.

## Quick start (developer)

1. Create venv and install
   - make venv

2. Run tests
   - make test

3. Start the API
   - make serve

4. Ingest docs for RAG (optional)
   - make ingest

## Code style and tests
- Python 3.11+
- Lint: `make lint` (uses ruff)
- Tests: `make test`
- Please keep tests deterministic; use stub embeddings and temp paths where possible.

## Commit hygiene
- Small, focused commits
- Update docs when adding endpoints or flags
- Keep `.env.example` in sync with new configuration

## Release checklist
- Tests green
- If you changed endpoints or schemas, run `make export-openapi` and commit `docs/openapi.yaml`
- README/docs updated

## Developer tips
- Makefile targets: `make venv | install | test | serve | lint | ingest | sweep | freeze | export-openapi`
- Example requests: see `scripts/curl_examples.sh`
