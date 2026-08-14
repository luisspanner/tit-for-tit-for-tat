import asyncio
import json
import time
from pathlib import Path

import pytest

from tournament.webapp import runs as runs_module
from tournament.webapp.runs import (
    RunAlreadyInProgress,
    RunState,
    _append_transcript,
    _build_llm_only_roster,
    emit,
    start_run,
)


@pytest.fixture(autouse=True)
def isolated_results_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    results_dir = tmp_path / "results"
    monkeypatch.setattr(runs_module, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(runs_module, "TRANSCRIPTS_PATH", results_dir / "llm_transcripts.jsonl")
    monkeypatch.setattr(runs_module, "RUNS", {})
    yield results_dir


def _run_and_wait(
    experiment: str,
    rounds: int | None = None,
    include_classics: bool = False,
    models: list[str] | None = None,
    repeats: int | None = None,
    timeout: float = 10.0,
):
    async def _go():
        run = start_run(experiment, rounds, include_classics, models, repeats)
        deadline = time.monotonic() + timeout
        while run.status == "running" and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        return run

    return asyncio.run(_go())


def test_classic_round_robin_writes_results_and_completes() -> None:
    run = _run_and_wait("classic_round_robin", rounds=2)

    assert run.status == "done"
    assert (runs_module.RESULTS_DIR / "matches.csv").exists()
    assert (runs_module.RESULTS_DIR / "standings.json").exists()
    event_types = [e["type"] for e in run.events]
    assert event_types[0] == "run_start"
    assert event_types[-1] == "run_complete"
    assert "match_start" in event_types
    assert "match_end" in event_types


def test_classic_round_robin_archives_results_under_run_id() -> None:
    run = _run_and_wait("classic_round_robin", rounds=2)

    archive_dir = runs_module.RESULTS_DIR / "runs" / run.run_id
    assert (archive_dir / "matches.csv").read_text() == (runs_module.RESULTS_DIR / "matches.csv").read_text()
    assert (archive_dir / "standings.json").read_text() == (
        runs_module.RESULTS_DIR / "standings.json"
    ).read_text()
    manifest = json.loads((archive_dir / "manifest.json").read_text())
    assert manifest["run_id"] == run.run_id
    assert manifest["experiment"] == "classic_round_robin"


def test_classic_round_robin_does_not_emit_round_events() -> None:
    run = _run_and_wait("classic_round_robin", rounds=2)

    assert not any(e["type"] == "round" for e in run.events)


def test_llm_round_robin_with_no_providers_configured_reports_run_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_ENABLED", raising=False)

    run = _run_and_wait("llm_round_robin", rounds=2)

    assert run.status == "error"
    assert run.events[-1]["type"] == "run_error"


def test_build_llm_only_roster_with_none_returns_unfiltered() -> None:
    all_strategies = _build_llm_only_roster(None)

    assert [s.name for s in all_strategies] == [s.name for s in _build_llm_only_roster()]


def test_build_llm_only_roster_filters_by_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")

    unfiltered = _build_llm_only_roster()
    assert [s.model_name for s in unfiltered] == ["qwen2.5"]

    filtered = _build_llm_only_roster(models=["some-other-model"])
    assert filtered == []


def test_last_round_experiment_run_archives_and_writes_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")

    class ScriptedClient:
        def complete(self, system_prompt: str, user_message: str) -> str:
            return "C - cooperating"

    monkeypatch.setattr(
        "tournament.llm_roster.ollama_local_client", lambda model="qwen2.5": ScriptedClient()
    )

    run = _run_and_wait("last_round_experiment", rounds=2, repeats=1)

    assert run.status == "done"
    assert (runs_module.RESULTS_DIR / "last_round_experiment.json").exists()
    event_types = [e["type"] for e in run.events]
    assert "lre_repeat_start" in event_types
    assert "lre_repeat_end" in event_types
    assert "lre_model_done" in event_types
    archive_dir = runs_module.RESULTS_DIR / "runs" / run.run_id
    assert (archive_dir / "last_round_experiment.json").exists()


def test_last_round_experiment_run_respects_models_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_ENABLED", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    class ScriptedClient:
        def complete(self, system_prompt: str, user_message: str) -> str:
            return "C - cooperating"

    monkeypatch.setattr(
        "tournament.llm_roster.groq_client", lambda model="llama-3.1-8b-instant": ScriptedClient()
    )

    run = _run_and_wait(
        "last_round_experiment", rounds=2, repeats=1, models=["llama-3.1-8b-instant"]
    )

    assert run.status == "done"
    summary = json.loads((runs_module.RESULTS_DIR / "last_round_experiment.json").read_text())
    assert set(summary.keys()) == {"llama-3.1-8b-instant"}


def test_second_run_while_one_in_progress_raises() -> None:
    async def _go():
        first = start_run("classic_round_robin", rounds=2, include_classics=False)
        with pytest.raises(RunAlreadyInProgress):
            start_run("classic_round_robin", rounds=2, include_classics=False)
        while first.status == "running":
            await asyncio.sleep(0.01)

    asyncio.run(_go())


def test_unknown_experiment_raises_value_error() -> None:
    async def _go():
        with pytest.raises(ValueError):
            start_run("not_a_real_experiment", rounds=2, include_classics=False)

    asyncio.run(_go())


def test_append_transcript_round_trips_moves_with_reasoning() -> None:
    result = {"model_a": "model-x", "model_b": "model-y", "rounds": 2, "score_a": 6, "score_b": 6}
    moves = [(0, "C", "D", "reciprocating", None), (1, "D", "D", None, "opponent defected")]

    _append_transcript("run-1", "llm_a", "llm_b", result, moves)

    lines = runs_module.TRANSCRIPTS_PATH.read_text().splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line["run_id"] == "run-1"
    assert line["moves"] == [[0, "C", "D", "reciprocating", None], [1, "D", "D", None, "opponent defected"]]


def test_emit_pushes_to_all_subscriber_queues() -> None:
    async def _go():
        loop = asyncio.get_running_loop()
        run = RunState(run_id="test", experiment="classic_round_robin", loop=loop)
        q1: asyncio.Queue = asyncio.Queue()
        q2: asyncio.Queue = asyncio.Queue()
        run.subscribers.add(q1)
        run.subscribers.add(q2)

        emit(run, {"type": "run_start"})
        await asyncio.sleep(0)  # let call_soon_threadsafe callbacks run

        assert run.events == [{"type": "run_start"}]
        assert q1.get_nowait() == {"type": "run_start"}
        assert q2.get_nowait() == {"type": "run_start"}

    asyncio.run(_go())
