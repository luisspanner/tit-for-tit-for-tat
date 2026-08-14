from pathlib import Path

import pytest

from tournament.last_round_experiment import run_last_round_experiment
from tournament.strategies.classic import AlwaysCooperate, TitForTat


class ScriptedClient:
    """Always defects on what it's told is the final round, cooperates otherwise -
    a stand-in for a model that genuinely reacts to the last-round notice."""

    def __init__(self) -> None:
        self.call_count = 0

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.call_count += 1
        return "D" if "final round" in user_message.lower() else "C"


def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_ENABLED", raising=False)


def test_run_last_round_experiment_with_no_providers_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)

    assert run_last_round_experiment("prompt", tmp_path) == {}


def test_run_last_round_experiment_detects_announcement_driven_defection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    monkeypatch.setattr(
        "tournament.llm_roster.ollama_local_client", lambda model="qwen2.5": ScriptedClient()
    )

    summary = run_last_round_experiment(
        "prompt",
        tmp_path,
        rounds=5,
        repeats=2,
        opponent_factories=[TitForTat, AlwaysCooperate],
    )

    assert set(summary.keys()) == {"qwen2.5"}
    result = summary["qwen2.5"]

    # ScriptedClient always defects on an announced last round, never otherwise -
    # so "told" should show 100% last-round defection, "untold" 0%.
    assert result["told"]["last_round_defect_rate"] == 1.0
    assert result["untold"]["last_round_defect_rate"] == 0.0
    assert result["told"]["last_round_total"] == 4  # 2 opponents x 2 repeats
    assert result["untold"]["last_round_total"] == 4
    assert result["z_score"] is not None
    assert result["p_value"] is not None

    # cooperation_by_round has one entry per round, and round 0 (never the
    # last round here) should show full cooperation under both conditions.
    assert len(result["told"]["cooperation_by_round"]) == 5
    assert result["told"]["cooperation_by_round"][0] == 1.0
    assert result["untold"]["cooperation_by_round"][0] == 1.0


def test_run_last_round_experiment_repeats_produce_independent_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    client = ScriptedClient()
    monkeypatch.setattr("tournament.llm_roster.ollama_local_client", lambda model="qwen2.5": client)

    run_last_round_experiment(
        "prompt", tmp_path, rounds=3, repeats=2, opponent_factories=[TitForTat]
    )

    # 2 conditions x 1 opponent x 2 repeats x 3 rounds = 12 live calls -
    # caching being disabled per-repeat means every one actually hit the client.
    assert client.call_count == 12


def test_run_last_round_experiment_filters_by_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        "tournament.llm_roster.groq_client", lambda model="llama-3.1-8b-instant": ScriptedClient()
    )

    summary = run_last_round_experiment(
        "prompt",
        tmp_path,
        rounds=2,
        repeats=1,
        opponent_factories=[TitForTat],
        models=["llama-3.1-8b-instant"],
    )

    assert set(summary.keys()) == {"llama-3.1-8b-instant"}


def test_run_last_round_experiment_fires_progress_callbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    monkeypatch.setattr(
        "tournament.llm_roster.ollama_local_client", lambda model="qwen2.5": ScriptedClient()
    )

    repeat_starts = []
    repeat_ends = []
    model_dones = []
    run_last_round_experiment(
        "prompt",
        tmp_path,
        rounds=2,
        repeats=1,
        opponent_factories=[TitForTat],
        on_repeat_start=lambda model, opponent, repeat: repeat_starts.append((model, opponent, repeat)),
        on_repeat_end=lambda model, opponent, repeat, moves: repeat_ends.append((model, opponent, repeat)),
        on_model_done=lambda model, result: model_dones.append(model),
    )

    # 2 conditions x 1 opponent x 1 repeat = 2 repeat_start/repeat_end events.
    assert len(repeat_starts) == 2
    assert len(repeat_ends) == 2
    assert model_dones == ["qwen2.5"]
