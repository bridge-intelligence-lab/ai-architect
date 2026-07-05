#!/usr/bin/env python3
"""LangSmith experiment harness for the Architect agent (LS-6/LS-8).

Streams each dataset example through GET /architect/stream (SSE), assembles
the payload contract from scripts/langsmith_evaluators.py, and runs the code
evaluators plus the four LLM judges via langsmith.evaluate().

Usage:
    # smoke run: 3 examples, code evaluators only
    python scripts/run_langsmith_eval.py --limit 3 --no-judges

    # full run with judges
    python scripts/run_langsmith_eval.py --experiment-prefix baseline-langgraph-1024

Env: LANGCHAIN_API_KEY (LangSmith), OPENAI_API_KEY (judges).
The current app config is recorded on the experiment via --agent-backend /
--max-tokens metadata flags (the harness cannot see the server's env).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from langsmith_evaluators import run_code_evaluators  # noqa: E402


def stream_architect(question: str, url: str, timeout: float, max_tokens: Optional[int]) -> Dict[str, Any]:
    """Consume the SSE stream and assemble the evaluator payload contract."""
    events_seen: List[str] = []
    collected: Dict[str, Any] = {"meta": {}, "summary": None, "steps": None, "citations": [], "audit": {}}
    start = time.monotonic()
    ttft: Optional[float] = None

    # Fresh session per example: with backend-agnostic memory, sharing the
    # implicit "default" session would leak conversation context across
    # dataset examples and contaminate groundedness.
    session_id = f"eval-{uuid.uuid4().hex[:12]}"
    with httpx.Client(timeout=timeout) as client:
        with client.stream(
            "GET",
            url,
            params={"question": question, "session_id": session_id},
            headers={"Accept": "text/event-stream"},
        ) as resp:
            resp.raise_for_status()
            current_event: Optional[str] = None
            data_buf: List[str] = []
            for line in resp.iter_lines():
                line = (line or "").strip()
                if line == "":
                    if current_event and data_buf:
                        # ttft = first content event; "status" is an instant ack
                        if ttft is None and current_event != "status":
                            ttft = time.monotonic() - start
                        events_seen.append(current_event)
                        try:
                            payload = json.loads("\n".join(data_buf))
                        except Exception:
                            payload = None
                        if current_event == "meta" and isinstance(payload, dict):
                            collected["meta"] = payload
                        elif current_event == "summary" and isinstance(payload, str):
                            collected["summary"] = payload
                        elif current_event == "steps" and isinstance(payload, list):
                            collected["steps"] = [str(x) for x in payload]
                        elif current_event == "citations" and isinstance(payload, list):
                            collected["citations"] = payload
                        elif current_event == "audit" and isinstance(payload, dict):
                            collected["audit"] = payload
                    current_event = None
                    data_buf = []
                elif line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    data_buf = []
                elif line.startswith("data:"):
                    data_buf.append(line.split(":", 1)[1].strip())

    collected["events_seen"] = events_seen
    collected["config"] = {"max_tokens": max_tokens}
    collected["timing"] = {"latency_s": round(time.monotonic() - start, 3), "ttft_s": round(ttft, 3) if ttft else None}
    return collected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="ai-architect-golden")
    parser.add_argument("--url", default="http://localhost:8000/architect/stream")
    parser.add_argument("--limit", type=int, default=0, help="run only the first N examples (0 = all)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--no-judges", action="store_true", help="code evaluators only (free, fast)")
    parser.add_argument("--experiment-prefix", default="architect-eval")
    parser.add_argument("--agent-backend", default=os.getenv("AGENT_BACKEND", "unknown"),
                        help="recorded as experiment metadata; must match the running server")
    parser.add_argument("--max-tokens", type=int, default=int(os.getenv("LLM_MAX_TOKENS", "0")) or None,
                        help="server's LLM_MAX_TOKENS; feeds the not_truncated evaluator")
    args = parser.parse_args()

    if not os.getenv("LANGCHAIN_API_KEY"):
        print("LANGCHAIN_API_KEY is not set", file=sys.stderr)
        return 1

    from langsmith import Client
    from langsmith.evaluation import evaluate

    client = Client()

    data = args.dataset
    if args.limit:
        examples = list(client.list_examples(dataset_name=args.dataset))
        examples.sort(key=lambda e: (e.metadata or {}).get("id", ""))
        data = examples[: args.limit]

    def target(inputs: Dict[str, Any]) -> Dict[str, Any]:
        return stream_architect(inputs["question"], args.url, args.timeout, args.max_tokens)

    def code_evaluators(run, example) -> Dict[str, Any]:
        return {"results": run_code_evaluators(run, example)}

    evaluators = [code_evaluators]
    if not args.no_judges:
        from langsmith_judges import ALL_JUDGES

        evaluators.extend(ALL_JUDGES)

    result = evaluate(
        target,
        data=data,
        evaluators=evaluators,
        experiment_prefix=args.experiment_prefix,
        metadata={
            "agent_backend": args.agent_backend,
            "max_tokens": args.max_tokens,
            "judges": not args.no_judges,
        },
        max_concurrency=2,  # be gentle: each target call is a live LLM request
    )
    print(f"\nexperiment: {result.experiment_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
