"""Offline tests for the LS-8 grid runner (scripts/run_experiment_grid.py)."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_experiment_grid as grid  # noqa: E402


ENV_TEMPLATE = """\
LLM_PROVIDER=openai
AGENT_BACKEND=langgraph
LLM_MAX_TOKENS=1024
RAG_BACKEND=vector
"""


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(ENV_TEMPLATE)
    monkeypatch.setattr(grid, "ENV_FILE", path)
    return path


def test_cell_name():
    assert grid.cell_name({"backend": "builtin", "max_tokens": 2048}) == "builtin-2048"


def test_grid_has_four_unique_cells():
    names = [grid.cell_name(c) for c in grid.CELLS]
    assert len(names) == 4
    assert len(set(names)) == 4


def test_set_env_values_rewrites_only_target_lines(env_file):
    grid.set_env_values("builtin", 2048)
    text = env_file.read_text()
    assert "AGENT_BACKEND=builtin" in text
    assert "LLM_MAX_TOKENS=2048" in text
    # untouched neighbours survive
    assert "LLM_PROVIDER=openai" in text
    assert "RAG_BACKEND=vector" in text


def test_set_env_values_requires_exactly_one_line(env_file):
    env_file.write_text(ENV_TEMPLATE + "AGENT_BACKEND=builtin\n")
    with pytest.raises(RuntimeError, match="exactly one"):
        grid.set_env_values("langgraph", 1024)


def test_set_env_values_missing_key(env_file):
    env_file.write_text("LLM_PROVIDER=openai\n")
    with pytest.raises(RuntimeError):
        grid.set_env_values("builtin", 1024)


def test_run_cell_parses_experiment_name(monkeypatch):
    res = SimpleNamespace(returncode=0, stdout="...\nexperiment: grid-builtin-1024-abc123\n", stderr="")
    monkeypatch.setattr(grid.subprocess, "run", lambda *a, **k: res)
    name = grid.run_cell({"backend": "builtin", "max_tokens": 1024}, "python")
    assert name == "grid-builtin-1024-abc123"


def test_run_cell_falls_back_to_prefix(monkeypatch):
    res = SimpleNamespace(returncode=0, stdout="no name here", stderr="")
    monkeypatch.setattr(grid.subprocess, "run", lambda *a, **k: res)
    assert grid.run_cell({"backend": "langgraph", "max_tokens": 2048}, "python") == "grid-langgraph-2048"


def test_run_cell_raises_on_failure(monkeypatch):
    res = SimpleNamespace(returncode=1, stdout="", stderr="boom")
    monkeypatch.setattr(grid.subprocess, "run", lambda *a, **k: res)
    with pytest.raises(RuntimeError, match="failed"):
        grid.run_cell({"backend": "builtin", "max_tokens": 1024}, "python")


def test_main_rejects_unknown_cell(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_experiment_grid.py", "--cells", "nope-42"])
    assert grid.main() == 1
    assert "no matching cells" in capsys.readouterr().err


def test_main_restores_env_on_cell_failure(env_file, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_experiment_grid.py", "--cells", "builtin-2048"])
    monkeypatch.setattr(grid, "trigger_reload_and_wait", lambda *a, **k: None)

    def boom(cell, python):
        raise RuntimeError("cell exploded")

    monkeypatch.setattr(grid, "run_cell", boom)
    with pytest.raises(RuntimeError, match="cell exploded"):
        grid.main()
    assert env_file.read_text() == ENV_TEMPLATE
