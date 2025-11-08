#!/usr/bin/env python3
import asyncio
import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

# LangSmith tracing disabled in script to avoid duplicate runs (server handles tracing)
ENABLE_LANGSMITH = False
LS_CLIENT = None


@dataclass
class EvalConfig:
    url: str = "http://localhost:8000/architect/stream"
    file: str = "eval/architect_prompts.jsonl"
    limit: int = 0  # 0 means all
    summary_min: int = 40
    steps_min: int = 2
    step_chars: int = 20
    timeout: float = 60.0


def load_prompts(path: str) -> List[str]:
    prompts: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                q = obj.get("question") or obj.get("prompt") or obj.get("q")
                if isinstance(q, str) and q.strip():
                    prompts.append(q.strip())
            except Exception:
                # fallback: treat the line as the prompt itself
                prompts.append(line)
    return prompts


async def stream_architect(question: str, url: str, timeout: float = 60.0, llm_model: Optional[str] = None) -> Dict[str, Any]:
    params = {"question": question}
    if llm_model:
        params["llm_model"] = llm_model
    meta: Dict[str, Any] = {}
    summary: Optional[str] = None
    steps: Optional[List[str]] = None
    citations: List[Dict[str, Any]] = []
    audit: Dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("GET", url, params=params, headers={"Accept": "text/event-stream"}) as resp:
            resp.raise_for_status()
            current_event: Optional[str] = None
            data_buf: List[str] = []
            async for line in resp.aiter_lines():
                if line is None:
                    continue
                line = line.strip()
                if line == "":
                    # end of event frame
                    if current_event and data_buf:
                        data_json = "\n".join(data_buf)
                        try:
                            payload = json.loads(data_json)
                        except Exception:
                            payload = None
                        if isinstance(payload, dict) or isinstance(payload, list) or isinstance(payload, str):
                            if current_event == "meta" and isinstance(payload, dict):
                                meta = payload
                            elif current_event == "summary" and isinstance(payload, str):
                                summary = payload
                            elif current_event == "steps" and isinstance(payload, list):
                                steps = [str(x) for x in payload]
                            elif current_event == "citations" and isinstance(payload, list):
                                citations = payload
                            elif current_event == "audit" and isinstance(payload, dict):
                                audit = payload
                    # reset for next event
                    current_event = None
                    data_buf = []
                    continue
                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    data_buf = []
                    continue
                if line.startswith("data:"):
                    data_buf.append(line.split(":", 1)[1].strip())
                    continue
                # ignore other fields (id:, retry:, etc.)
    return {"meta": meta, "summary": summary, "steps": steps, "citations": citations, "audit": audit}


def score_result(result: Dict[str, Any], cfg: EvalConfig) -> Dict[str, Any]:
    summary = result.get("summary") or ""
    steps = result.get("steps") or []
    # Basic scoring
    s_len = len(summary.strip())
    steps_ok = isinstance(steps, list) and len(steps) >= cfg.steps_min
    steps_lengths = [len(str(s).strip()) for s in steps]
    steps_chars_ok = all(length >= cfg.step_chars for length in steps_lengths) if steps else False
    summary_ok = s_len >= cfg.summary_min

    scores = {
        "summary_len": s_len,
        "steps_count": len(steps),
        "steps_lengths": steps_lengths,
        "summary_ok": summary_ok,
        "steps_ok": steps_ok,
        "steps_chars_ok": steps_chars_ok,
        "pass": bool(summary_ok and steps_ok and steps_chars_ok),
    }
    return scores


def maybe_trace_langsmith(question: str, result: Dict[str, Any], scores: Dict[str, Any]):
    if not ENABLE_LANGSMITH or LS_CLIENT is None:
        return
    try:
        meta = result.get("meta") or {}
        ls_meta = {
            "provider": meta.get("provider"),
            "model": meta.get("model"),
            "grounded_used": meta.get("grounded_used"),
        }
        LS_CLIENT.create_run(
            name="architect_eval",
            inputs={"question": question},
            outputs={
                "meta": meta,
                "summary": result.get("summary"),
                "steps": result.get("steps"),
                "citations": result.get("citations"),
                "audit": result.get("audit"),
                "scores": scores,
            },
            extra=ls_meta,
        )
    except Exception:
        pass


async def main():
    parser = argparse.ArgumentParser(description="Live eval for Architect SSE using httpx")
    parser.add_argument("--url", default="http://localhost:8000/architect/stream")
    parser.add_argument("--file", default="eval/architect_prompts.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="number of prompts to run (0 = all)")
    parser.add_argument("--summary-min", type=int, default=40)
    parser.add_argument("--steps-min", type=int, default=2)
    parser.add_argument("--step-chars", type=int, default=20)
    parser.add_argument("--llm-model", dest="llm_model", default=None, help="Override model for this eval run")
    args = parser.parse_args()

    cfg = EvalConfig(
        url=args.url,
        file=args.file,
        limit=args.limit,
        summary_min=args.summary_min,
        steps_min=args.steps_min,
        step_chars=args.step_chars,
    )

    prompts = load_prompts(cfg.file)
    if cfg.limit > 0:
        prompts = prompts[: cfg.limit]

    if not prompts:
        print(f"No prompts found in {cfg.file}")
        return

    results: List[Dict[str, Any]] = []
    passes = 0

    for i, q in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] Evaluating: {q[:80]}...")
        try:
            res = await stream_architect(q, cfg.url, timeout=cfg.timeout, llm_model=args.llm_model)
        except Exception as e:
            print(f"  Error: {e}")
            continue
        scores = score_result(res, cfg)
        maybe_trace_langsmith(q, res, scores)
        passed = scores.get("pass", False)
        passes += int(bool(passed))
        results.append({"question": q, "result": res, "scores": scores})
        # Compact print
        meta = res.get("meta") or {}
        print(
            f"  model={meta.get('model')} provider={meta.get('provider')} "
            f"summary_len={scores['summary_len']} steps={scores['steps_count']} pass={passed}"
        )

    # Summary
    total = len(results)
    print("\n=== Evaluation Summary ===")
    print(f"Total: {total}")
    print(f"Passes: {passes}")
    if total:
        print(f"Pass rate: {passes/total:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
