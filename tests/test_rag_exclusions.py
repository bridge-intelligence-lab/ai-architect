"""RAG corpus exclusions (RAG_EXCLUDE_FILES / RAG_EXCLUDE_DIRS): the
test-prompt list and work-record dirs must never be retrieved as grounding
context."""
import os
import sys
from pathlib import Path

from app.services.doc_retriever import answer_with_citations, excluded_files, is_excluded

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _corpus(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "audit.md").write_text("Audit rows are written by write_audit with retention settings.")
    (docs / "llm_agent_streaming_prompts.md").write_text(
        "Where are audit rows written and which fields are tracked? "
        "How do I configure retention and metrics?"
    )
    return docs


def test_default_excludes_prompt_list():
    assert is_excluded("llm_agent_streaming_prompts.md")
    assert is_excluded("/some/dir/LLM_Agent_Streaming_Prompts.md")  # case + path insensitive
    assert not is_excluded("audit.md")


def test_env_override(monkeypatch):
    monkeypatch.setenv("RAG_EXCLUDE_FILES", "a.md, B.md")
    assert excluded_files() == {"a.md", "b.md"}
    assert is_excluded("b.md")
    assert not is_excluded("llm_agent_streaming_prompts.md")


def test_keyword_scan_never_cites_excluded_file(monkeypatch, tmp_path):
    docs = _corpus(tmp_path)
    monkeypatch.setenv("DOCS_PATH", str(docs))
    # the excluded file matches the question verbatim; it must still not appear
    res = answer_with_citations("Where are audit rows written and how do I configure retention?")
    sources = [c["source"] for c in res["citations"]]
    assert sources, "expected the real doc to match"
    assert all("llm_agent_streaming_prompts" not in s for s in sources)


def test_fallback_paths_skip_excluded_file(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    # ONLY the excluded file exists: fallback must not resurrect it
    (docs / "llm_agent_streaming_prompts.md").write_text("prompt list content")
    monkeypatch.setenv("DOCS_PATH", str(docs))
    res = answer_with_citations("zzz nothing matches this")
    assert res["citations"] == []


def test_ingest_iter_documents_skips_excluded(monkeypatch, tmp_path, capsys):
    docs = _corpus(tmp_path)
    from ingest_docs import iter_documents

    paths = [p for p, _ in iter_documents(str(docs))]
    assert any(p.endswith("audit.md") for p in paths)
    assert not any("llm_agent_streaming_prompts" in p for p in paths)
    assert "exclude" in capsys.readouterr().out


def test_worklog_dir_excluded_by_default(monkeypatch, tmp_path):
    assert is_excluded("docs/worklog/2026-07-04-docs-knowledge-backlog.md")
    assert is_excluded("/abs/path/docs/WORKLOG/anything.md")  # case-insensitive
    assert not is_excluded("docs/worklog.md")  # a file named worklog is not a dir match

    docs = tmp_path / "docs"
    (docs / "worklog").mkdir(parents=True)
    (docs / "rag.md").write_text("RAG backends are configured via RAG_BACKEND.")
    (docs / "worklog" / "2026-07-04-report.md").write_text(
        "RAG backends were reviewed today; RAG_BACKEND findings and backlog."
    )
    monkeypatch.setenv("DOCS_PATH", str(docs))
    res = answer_with_citations("How are RAG backends configured?")
    sources = [c["source"] for c in res["citations"]]
    assert sources, "expected the real doc to match"
    assert all("worklog" not in s for s in sources)

    from ingest_docs import iter_documents

    paths = [p for p, _ in iter_documents(str(docs))]
    assert any(p.endswith("rag.md") for p in paths)
    assert not any(f"{os.sep}worklog{os.sep}" in p for p in paths)


def test_exclude_dirs_env_override(monkeypatch):
    monkeypatch.setenv("RAG_EXCLUDE_DIRS", "internal, Drafts")
    assert is_excluded("docs/internal/notes.md")
    assert is_excluded("docs/drafts/x.md")
    assert not is_excluded("docs/worklog/x.md")  # default replaced by override


def test_vector_query_filters_stale_excluded_chunks(monkeypatch):
    from app.services import vector_retriever

    class FakeCol:
        def query(self, **kwargs):
            return {
                "ids": [["a", "b"]],
                "documents": [["prompt list text", "real audit text"]],
                "metadatas": [[{"source": "llm_agent_streaming_prompts.md"}, {"source": "audit.md"}]],
                "distances": [[0.1, 0.2]],
            }

    class FakeEmb:
        def embed(self, texts):
            return [[0.0]]

    monkeypatch.setattr(vector_retriever, "get_collection", lambda create=False: FakeCol())
    monkeypatch.setattr(vector_retriever, "get_embedder", lambda: FakeEmb())
    citations = vector_retriever.query("audit?", k=1)
    assert [c["source"] for c in citations] == ["audit.md"]
