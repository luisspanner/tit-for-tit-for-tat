from pathlib import Path

import pytest

from tournament.llm_roster import GROQ_MODELS, OLLAMA_CLOUD_MODELS, build_llm_strategies, configured_model_names


def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_ENABLED", raising=False)


def test_no_providers_configured_returns_empty_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)

    assert build_llm_strategies("prompt", tmp_path) == []


def test_configured_model_names_with_no_providers_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)

    assert configured_model_names() == []


def test_configured_model_names_reflects_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_ENABLED", "1")

    names = configured_model_names()

    assert names == ["claude-sonnet-5", *GROQ_MODELS, "qwen2.5"]


def test_configured_model_names_includes_ollama_cloud_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    assert configured_model_names() == OLLAMA_CLOUD_MODELS


def test_anthropic_key_adds_one_strategy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    strategies = build_llm_strategies("prompt", tmp_path)

    assert [s.name for s in strategies] == ["llm_claude_sonnet_5"]
    assert strategies[0].model_name == "claude-sonnet-5"


def test_groq_key_adds_all_model_tiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    strategies = build_llm_strategies("prompt", tmp_path)

    assert [s.name for s in strategies] == [
        "llm_groq_llama_3_1_8b_instant",
        "llm_groq_llama_3_3_70b_versatile",
    ]
    assert [s.model_name for s in strategies] == [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
    ]


def test_ollama_api_key_adds_cloud_model_tiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    strategies = build_llm_strategies("prompt", tmp_path)

    assert [s.name for s in strategies] == ["llm_ollama_cloud_gemma4_31b_cloud"]
    assert [s.model_name for s in strategies] == ["gemma4:31b-cloud"]


def test_ollama_enabled_adds_one_local_strategy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")

    strategies = build_llm_strategies("prompt", tmp_path)

    assert [s.name for s in strategies] == ["llm_ollama_local_qwen2_5"]
    assert strategies[0].model_name == "qwen2.5"


def test_all_providers_configured_adds_distinct_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_ENABLED", "1")

    strategies = build_llm_strategies("prompt", tmp_path)

    names = [s.name for s in strategies]
    # 1 anthropic + 2 groq + 1 ollama cloud + 1 ollama local = 5
    assert len(names) == len(set(names)) == 5


def test_each_strategy_gets_its_own_cache_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    strategies = build_llm_strategies("prompt", tmp_path)

    cache_paths = {s.cache.path for s in strategies}
    assert len(cache_paths) == 2


def test_announce_last_round_false_suffixes_names_and_cache_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    told = build_llm_strategies("prompt", tmp_path, announce_last_round=True)
    untold = build_llm_strategies("prompt", tmp_path, announce_last_round=False)

    assert [s.name for s in untold] == [
        "llm_groq_llama_3_1_8b_instant_untold",
        "llm_groq_llama_3_3_70b_versatile_untold",
    ]
    assert all(s.announce_last_round is False for s in untold)
    assert all(s.announce_last_round is True for s in told)

    told_paths = {s.cache.path for s in told}
    untold_paths = {s.cache.path for s in untold}
    assert told_paths.isdisjoint(untold_paths)
