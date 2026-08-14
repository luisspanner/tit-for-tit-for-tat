from pathlib import Path

import pytest

from tournament.cache import DiskCache, cache_key
from tournament.opponent_is_ai_experiment import run_opponent_is_ai_experiment
from tournament.strategies.classic import AlwaysCooperate, TitForTat


class ScriptedClient:
    """Defects iff the AI-reveal sentence appears in the system prompt - a
    stand-in for a model that reacts to knowing its opponent is an AI."""

    def __init__(self) -> None:
        self.call_count = 0

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.call_count += 1
        if "also an AI system" in system_prompt:
            return "D - opponent is AI, no reputational stakes"
        return "C - reciprocating"


def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_ENABLED", raising=False)


def _write_prompts(prompts_dir: Path) -> None:
    (prompts_dir / "baseline.txt").write_text("baseline prompt")
    (prompts_dir / "opponent_is_ai.txt").write_text("baseline prompt. also an AI system.")


def test_run_opponent_is_ai_experiment_with_no_providers_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    _write_prompts(tmp_path)

    assert run_opponent_is_ai_experiment(tmp_path, tmp_path) == {}


def test_run_opponent_is_ai_experiment_detects_ai_reveal_driven_defection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    _write_prompts(tmp_path)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    monkeypatch.setattr(
        "tournament.llm_roster.ollama_local_client", lambda model="qwen2.5": ScriptedClient()
    )

    summary = run_opponent_is_ai_experiment(
        tmp_path, tmp_path, rounds=5, repeats=2, opponent_factories=[TitForTat, AlwaysCooperate]
    )

    assert set(summary.keys()) == {"qwen2.5"}
    result = summary["qwen2.5"]

    assert result["baseline"]["cooperation_rate"] == 1.0
    assert result["ai_revealed"]["cooperation_rate"] == 0.0
    assert result["baseline"]["total_moves"] == 20  # 2 opponents x 2 repeats x 5 rounds
    assert result["ai_revealed"]["total_moves"] == 20
    assert result["z_score"] is not None
    assert result["p_value"] is not None


def test_run_opponent_is_ai_experiment_repeats_produce_independent_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    _write_prompts(tmp_path)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    client = ScriptedClient()
    monkeypatch.setattr("tournament.llm_roster.ollama_local_client", lambda model="qwen2.5": client)

    run_opponent_is_ai_experiment(tmp_path, tmp_path, rounds=3, repeats=2, opponent_factories=[TitForTat])

    # 2 conditions x 1 opponent x 2 repeats x 3 rounds = 12 live calls -
    # caching being disabled per-repeat means every one actually hit the client.
    assert client.call_count == 12


def test_run_opponent_is_ai_experiment_fires_progress_callbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    _write_prompts(tmp_path)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    monkeypatch.setattr(
        "tournament.llm_roster.ollama_local_client", lambda model="qwen2.5": ScriptedClient()
    )

    repeat_starts = []
    repeat_ends = []
    model_dones = []
    run_opponent_is_ai_experiment(
        tmp_path,
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


def test_cache_key_separates_baseline_and_ai_reveal_prompts(tmp_path: Path) -> None:
    baseline_key = cache_key("baseline prompt", [], is_last_round=False, model="qwen2.5")
    ai_reveal_key = cache_key("baseline prompt. also an AI system.", [], is_last_round=False, model="qwen2.5")

    assert baseline_key != ai_reveal_key

    cache = DiskCache(tmp_path / "cache.json")
    cache.set(baseline_key, "C - reciprocating")
    assert cache.get(ai_reveal_key) is None
