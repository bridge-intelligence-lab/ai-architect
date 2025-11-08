import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from langchain_core.output_parsers import PydanticOutputParser
from app.services.llm_client import LLMClient
from app.services.architect_schema import ArchitectPlan
from app.services.langchain_rag import answer_with_citations

# Optional LangSmith tracing (env-gated)
from app.utils.logger import get_logger as _get_logger
_arch_logger = _get_logger("architect")
_ENABLE_LS = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true", "yes", "on") and bool(os.getenv("LANGCHAIN_API_KEY"))
_LS_PROJECT = os.getenv("LANGCHAIN_PROJECT")
_LS_SESSION = os.getenv("LANGCHAIN_TRACING_SESSION_NAME")
try:
    if _ENABLE_LS:
        from langsmith.run_trees import RunTree as _LSRunTree  # type: ignore
    else:
        _LSRunTree = None  # type: ignore
except Exception:
    _LSRunTree = None  # type: ignore


def _build_messages(question: str, plan_parser: PydanticOutputParser, context_blocks: List[str] | None = None) -> List[Dict[str, str]]:
    context_blocks = context_blocks or []
    fmt = plan_parser.get_format_instructions()
    system = (
        "You are the solution architect assistant for the AI-Architect project. "
        "Respond ONLY with a JSON object that matches the provided schema. "
        "Your JSON MUST include both 'summary' (string) and 'suggested_steps' (array of strings). "
        "If you cannot provide a value, set summary to an empty string and suggested_steps to an empty array. "
        "Do not include any fields outside the schema; do not include explanations outside JSON."
    )
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "system", "content": fmt},
    ]
    if context_blocks:
        ctx = "\n\n".join(context_blocks[:3])  # keep concise
        messages.append({"role": "system", "content": f"Context (for grounding):\n{ctx}"})
    messages.append({"role": "user", "content": question})
    return messages


def run_architect_agent(question: str, session_id: str | None = None, user_id: str | None = None, llm_model: str | None = None) -> Tuple[ArchitectPlan, Dict[str, Any]]:
    # Initialize memory flags and counters
    short_enabled = os.getenv("MEMORY_SHORT_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    long_enabled = os.getenv("MEMORY_LONG_ENABLED", "false").lower() in ("1", "true", "yes", "on")

    memory_short_reads = 0
    memory_short_writes = 0
    memory_short_pruned = 0
    summary_updated = False
    memory_long_reads = 0
    memory_long_writes = 0
    memory_long_pruned = 0

    uid = user_id or "anonymous"
    sid = session_id or "default"

    # Keep original question; build separate context blocks for memory
    original_question = question
    memory_context_block: str | None = None
    facts_context_block: str | None = None

    # 1a) Short-term memory: load conversation history
    if short_enabled:
        try:
            from app.memory.short_memory import init_short_memory, load_summary, load_turns

            init_short_memory()
            turns = load_turns(uid, sid)
            memory_short_reads = len(turns)
            memory_short_pruned = int(getattr(load_turns, "_last_pruned", 0))
            prefix = load_summary(uid, sid) or "\n".join(f"{r}: {c}" for r, c in turns[-5:])  # last 5 turns
            if prefix:
                memory_context_block = f"Conversation context:\n{prefix}"
            # Note: do not bump router-level globals from service; keep metrics in audit only
        except Exception as e:
            if os.getenv("MEMORY_DEBUG", "").lower() in ("1","true","yes","on"):
                try:
                    print(f"[MEMORY_DEBUG] memory op error: {e}")
                except Exception:
                    pass
            pass

    # 1b) Long-term memory: retrieve relevant facts
    if long_enabled:
        try:
            from app.memory.long_memory import retrieve_facts

            facts = retrieve_facts(uid, original_question, top_k=5)
            memory_long_reads = len(facts)
            memory_long_pruned = int(getattr(retrieve_facts, "_last_pruned", 0))
            if facts:
                snippet = "\n".join(f"- {f['text']}" for f in facts)
                facts_context_block = f"Relevant background facts:\n{snippet}"
            # Note: do not bump router-level globals from service; keep metrics in audit only
        except Exception as e:
            if os.getenv("MEMORY_DEBUG", "").lower() in ("1","true","yes","on"):
                try:
                    print(f"[MEMORY_DEBUG] memory op error: {e}")
                except Exception:
                    pass
            pass

    # 2) Retrieval
    citations: List[Dict[str, Any]] = []
    rag_meta: Dict[str, Any] = {}

    docs_path = os.getenv("DOCS_PATH") or "./docs"
    os.environ["DOCS_PATH"] = docs_path
    rag = answer_with_citations(question, k=3)
    citations = rag.get("citations", [])
    for k in ("rag_multi_query", "rag_multi_count", "rag_hyde"):
        if k in rag:
            rag_meta[k] = rag[k]

    grounded_used = bool(citations)
    rag_lines: List[str] = []
    if grounded_used:
        # Make compact context lines
        for c in citations[:3]:
            title = c.get("source") or c.get("path") or "doc"
            snippet = (c.get("snippet") or "").strip().replace("\n", " ")
            if snippet:
                snippet = snippet[:400]
            rag_lines.append(f"- {title}: {snippet}")

    # Build final context blocks: memory (short), facts (long), then RAG
    final_context: List[str] = []
    if memory_context_block:
        final_context.append(memory_context_block)
    if facts_context_block:
        final_context.append(facts_context_block)
    if grounded_used and rag_lines:
        final_context.append("Grounding:\n" + "\n".join(rag_lines))

    # 2) Build messages with structured format instructions
    parser = PydanticOutputParser(pydantic_object=ArchitectPlan)
    messages = _build_messages(original_question, parser, final_context if final_context else None)

    # 3) Call LLM
    llm = LLMClient()

    # Optional: start LangSmith run
    ls_run = None
    ls_run_id = None
    if _LSRunTree:
        try:
            _arch_logger.info("ls.run_tree start", extra={"extra": {"project": _LS_PROJECT, "session": _LS_SESSION}})
            ls_inputs = {"question": original_question, "context_blocks": final_context}
            ls_run = _LSRunTree(name="architect_server", run_type="chain", project=_LS_PROJECT, inputs=ls_inputs)
            ls_run_id = getattr(ls_run, "id", None)
            ls_run.post()
            _arch_logger.info("ls.run_tree posted", extra={"extra": {"run_id": ls_run_id}})
        except Exception as _e:
            _arch_logger.info("ls.run_tree failed", extra={"extra": {"error": str(_e)}})
            ls_run = None

    call_kwargs: Dict[str, Any] = {}
    if llm_model:
        call_kwargs["model"] = llm_model
    result = llm.call(messages, **call_kwargs)

    # 4) Parse structured output (fallback to defaults on error)
    text = result.get("text") or ""
    try:
        plan = parser.parse(text)
    except Exception:
        # fallback: try to construct directly if text is already JSON-like
        try:
            import json as _json

            data = _json.loads(text) if isinstance(text, str) else {}
            plan = ArchitectPlan(**data) if isinstance(data, dict) else ArchitectPlan()
        except Exception:
            plan = ArchitectPlan()

    # Post-parse guardrails: ensure fields are non-null, but do not synthesize content
    try:
        if getattr(plan, "summary", None) is None:
            plan.summary = ""
        if getattr(plan, "suggested_steps", None) is None:
            plan.suggested_steps = []
    except Exception:
        # Never fail the request due to guardrail adjustments
        pass

    # 5) Attach citations if grounded
    if grounded_used:
        plan.citations = citations
        plan.grounded_used = True

    # Complete LangSmith run with outputs (if enabled)
    if ls_run and ls_run_id:
        try:
            ls_outputs = {
                "summary": plan.summary,
                "steps": plan.suggested_steps,
                "citations": plan.citations,
                "audit": {
                    "llm_model": llm_model or llm.model,
                    "memory_short_reads": memory_short_reads,
                    "memory_long_reads": memory_long_reads,
                },
            }
            ls_run.end(outputs=ls_outputs, end_time=datetime.now(timezone.utc))
            _arch_logger.info("ls.run_tree end ok", extra={"extra": {"run_id": ls_run_id}})
        except Exception as _e:
            _arch_logger.info("ls.run_tree end failed", extra={"extra": {"error": str(_e), "run_id": ls_run_id}})

    # Light heuristic for feature suggestion
    try:
        ql = (question or "").lower()
        needs = any(w in ql for w in ("feature", "support", "integrate", "add", "roadmap"))
        sparse = len(plan.suggested_steps or []) == 0 and len(plan.suggested_env_flags or []) == 0
        if (sparse or not grounded_used) and needs:
            plan.suggest_feature = True
            plan.feature_request = plan.feature_request or (
                f"Request: {question[:60]}" if question else "Feature request"
            )
            plan.tone_hint = plan.tone_hint or ("exploratory" if not grounded_used else "actionable")
    except Exception as e:
            if os.getenv("MEMORY_DEBUG", "").lower() in ("1","true","yes","on"):
                try:
                    print(f"[MEMORY_DEBUG] memory op error: {e}")
                except Exception:
                    pass
            pass

    # 6) Save to memory after generating plan
    if short_enabled:
        try:
            from app.memory.short_memory import save_turn, update_summary_if_needed

            save_turn(uid, sid, "user", original_question)
            # Save plan summary as assistant response
            assistant_response = plan.summary or "Generated architecture plan."
            save_turn(uid, sid, "assistant", assistant_response)
            memory_short_writes = 2
            summary_updated = update_summary_if_needed(uid, sid)
        except Exception as e:
            if os.getenv("MEMORY_DEBUG", "").lower() in ("1","true","yes","on"):
                try:
                    print(f"[MEMORY_DEBUG] memory op error: {e}")
                except Exception:
                    pass
            pass

    if long_enabled:
        try:
            from app.memory.long_memory import ingest_fact

            # Ingest summary
            if plan.summary and len(plan.summary) > 50:
                ingest_fact(uid, plan.summary)
                memory_long_writes += 1

            # Ingest suggested steps
            for step in (plan.suggested_steps or []):
                if len(step) > 50:
                    ingest_fact(uid, step)
                    memory_long_writes += 1

            # Ingest feature request if present
            if plan.feature_request and len(plan.feature_request) > 50:
                ingest_fact(uid, plan.feature_request)
                memory_long_writes += 1
        except Exception as e:
            if os.getenv("MEMORY_DEBUG", "").lower() in ("1","true","yes","on"):
                try:
                    print(f"[MEMORY_DEBUG] memory op error: {e}")
                except Exception:
                    pass
            pass

    # 7) Build audit fields with memory counters
    audit: Dict[str, Any] = {
        "llm_provider": result.get("provider"),
        "llm_model": result.get("model"),
        "llm_tokens_prompt": result.get("tokens_prompt"),
        "llm_tokens_completion": result.get("tokens_completion"),
        "llm_cost_usd": result.get("cost_usd"),
        **rag_meta,
        "memory_short_reads": int(memory_short_reads or 0),
        "memory_short_writes": int(memory_short_writes or 0),
        "memory_short_pruned": int(memory_short_pruned or 0),
        "summary_updated": bool(summary_updated),
        "memory_long_reads": int(memory_long_reads or 0),
        "memory_long_writes": int(memory_long_writes or 0),
        "memory_long_pruned": int(memory_long_pruned or 0),
    }

    return plan, audit
