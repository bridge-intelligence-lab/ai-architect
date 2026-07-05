---
title: "ADR 0006: Native structured outputs; drop langchain, keep langchain-core"
status: current
module: architecture
last_reviewed: 2026-07-05
decision_date: 2026-07-04
adr_status: Accepted
---

# ADR 0006: Native structured outputs; drop langchain, keep langchain-core

## Context

- `pyproject.toml` pinned `langchain==0.1.11` (early 2024). The only code
  importing the full `langchain` package was
  `app/services/prompt_runner.py`, which turned out to be dead code: no
  module or test imports it, and its `LC_USE_OUTPUT_PARSER` flag is read
  nowhere else. It contained `parse_json_safe`, a ~95-line hand-rolled
  tolerant JSON extractor (fence stripping, quote unwrapping, escape repair,
  balanced-brace scanning, `ast.literal_eval`), plus a thin
  `JsonOutputParser` wrapper.
- The live structured-output path is `architect_agent.run_architect_agent`:
  it builds format instructions with `langchain_core`'s
  `PydanticOutputParser` over the `ArchitectPlan` pydantic model, parses the
  LLM text with it, and falls back to `json.loads` + `ArchitectPlan(**data)`
  with schema-level guardrails. That is already model-validated, typed
  output; it needs `langchain-core` only.

## Decision

- Delete `app/services/prompt_runner.py` (`parse_json_safe`,
  `parse_with_langchain_schema`, `run_prompt_as_chat`,
  `extract_architect_fields`) rather than porting it: schema validation with
  pydantic replaces tolerant string surgery, and the live path already does
  this.
- Drop the `langchain==0.1.11` dependency. Keep `langchain-core` as the only
  LangChain dist, used solely for typed output parsing
  (`PydanticOutputParser`). This follows the build-vs-buy call in
  [ADR-0004](0004-build-vs-buy.md).
- Provider-side structured outputs (JSON mode / tool-use enforced by the
  model API) become practical once the LLM client moves to LiteLLM (plan
  row E); the parsing seam in `architect_agent` is where they will plug in.

## Consequences

- The stale early-2024 pin is gone; a fresh install resolves a current
  `langchain-core` only, which shrinks the dependency tree.
- Behavior is unchanged: no live code path is modified, only removed. The
  `LC_USE_OUTPUT_PARSER` env flag no longer exists.
- The prompt registry (`app/utils/prompts.py`, `prompts/`) is untouched;
  it never depended on prompt_runner.
