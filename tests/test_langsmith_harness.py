"""Offline tests for the LS-6 harness and judges (no network, no LLM)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from run_langsmith_eval import stream_architect  # noqa: E402
import langsmith_judges as judges  # noqa: E402

SSE_BODY = (
    b"event: meta\ndata: {\"model\": \"stub\", \"grounded_used\": true}\n\n"
    b"event: summary\ndata: \"A plan summary that is long enough to pass checks.\"\n\n"
    b"event: steps\ndata: [\"Set the flag in .env and restart\", \"Verify via /architect\"]\n\n"
    b"event: citations\ndata: [{\"source\": \"docs/config.md\", \"snippet\": \"flags...\"}]\n\n"
    b"event: audit\ndata: {\"llm_tokens_completion\": 100}\n\n"
)


def _mock_stream(body: bytes = SSE_BODY):
    def handler(request):
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    return httpx.MockTransport(handler)


def test_stream_architect_assembles_payload_contract():
    transport = _mock_stream()
    real_client = httpx.Client

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    with patch("run_langsmith_eval.httpx.Client", side_effect=client_factory):
        out = stream_architect("q", "http://test/architect/stream", timeout=5, max_tokens=1024)

    assert out["events_seen"] == ["meta", "summary", "steps", "citations", "audit"]
    assert out["meta"]["grounded_used"] is True
    assert out["summary"].startswith("A plan summary")
    assert out["steps"] == ["Set the flag in .env and restart", "Verify via /architect"]
    assert out["citations"][0]["source"] == "docs/config.md"
    assert out["audit"]["llm_tokens_completion"] == 100
    assert out["config"] == {"max_tokens": 1024}
    assert out["timing"]["latency_s"] is not None
    assert out["timing"]["ttft_s"] is not None


def test_stream_architect_tolerates_malformed_event():
    body = b"event: meta\ndata: not-json\n\nevent: audit\ndata: {}\n\n"
    transport = _mock_stream(body)
    real_client = httpx.Client

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    with patch("run_langsmith_eval.httpx.Client", side_effect=client_factory):
        out = stream_architect("q", "http://test/x", timeout=5, max_tokens=None)

    assert out["events_seen"] == ["meta", "audit"]
    assert out["meta"] == {}  # malformed payload dropped, event still counted


def test_render_payload_includes_answer_and_context():
    text = judges._render_payload(
        {
            "summary": "s",
            "steps": ["a"],
            "meta": {"grounded_used": False},
            "citations": [{"source": "docs/x.md", "snippet": "y" * 400}],
        }
    )
    assert '"summary": "s"' in text
    assert "docs/x.md" in text
    assert len(text) < 1000  # snippet capped


def test_render_payload_no_citations():
    assert "Retrieved context: (none)" in judges._render_payload({"summary": None})


def test_judge_parses_llm_json(monkeypatch):
    def fake_completion(**kwargs):
        msg = SimpleNamespace(content=json.dumps({"score": 7, "reasoning": "clamped"}))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    import litellm

    monkeypatch.setattr(litellm, "completion", fake_completion)
    result = judges._judge_once("judge_correctness", "q", {"summary": "s"}, {})
    assert result == {"key": "judge_correctness", "score": 5, "comment": "clamped"}  # clamped to 1-5


def test_judge_expected_behavior_reaches_prompt(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured["user"] = kwargs["messages"][1]["content"]
        msg = SimpleNamespace(content=json.dumps({"score": 2, "reasoning": "r"}))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    import litellm

    monkeypatch.setattr(litellm, "completion", fake_completion)
    judges._judge_once(
        "judge_groundedness", "redis?", {"summary": "s"}, {"expected_behavior": "Says no Redis cache exists"}
    )
    assert "Says no Redis cache exists" in captured["user"]


def test_judge_evaluator_survives_llm_error(monkeypatch):
    import litellm

    def boom(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(litellm, "completion", boom)
    run = SimpleNamespace(outputs={"summary": "s"})
    example = SimpleNamespace(inputs={"question": "q"}, metadata={})
    result = judges.judge_correctness(run, example)
    assert result["score"] is None
    assert "provider down" in result["comment"]


def test_all_judges_have_distinct_keys():
    keys = {j.__name__ for j in judges.ALL_JUDGES}
    assert keys == {"judge_correctness", "judge_groundedness", "judge_completeness", "judge_actionability"}
