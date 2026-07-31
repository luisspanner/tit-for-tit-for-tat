from pathlib import Path

import pytest

from tournament.cache import DiskCache
from tournament.strategies.llm import LLMStrategy, parse_move, render_history


class StubClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.call_count = 0
        self.last_system_prompt: str | None = None
        self.last_user_message: str | None = None

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.call_count += 1
        self.last_system_prompt = system_prompt
        self.last_user_message = user_message
        return self.response


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("C", "C"),
        ("D", "D"),
        ("c", "C"),
        (" D\n", "D"),
        ("Cooperate", "C"),
        ("I will Defect.", "D"),
    ],
)
def test_parse_move_handles_common_response_shapes(raw: str, expected: str) -> None:
    assert parse_move(raw) == expected


def test_parse_move_raises_on_unparseable_response() -> None:
    with pytest.raises(ValueError):
        parse_move("I'm not sure what to do here.")


def test_render_history_empty() -> None:
    assert "round 1" in render_history([]).lower()


def test_render_history_includes_past_rounds() -> None:
    text = render_history([("C", "D"), ("D", "D")])
    assert "Round 1: You: C, Opponent: D" in text
    assert "Round 2: You: D, Opponent: D" in text


def test_llm_strategy_returns_parsed_move_from_client() -> None:
    client = StubClient(response="D")
    strategy = LLMStrategy(name="stub", system_prompt="be ruthless", client=client)

    assert strategy.move([]) == "D"
    assert client.call_count == 1
    assert client.last_system_prompt == "be ruthless"


def test_llm_strategy_never_calls_client_twice_for_same_state(tmp_path: Path) -> None:
    client = StubClient(response="C")
    cache = DiskCache(tmp_path / "cache.json")
    strategy = LLMStrategy(name="stub", system_prompt="be nice", client=client, cache=cache)

    assert strategy.move([]) == "C"
    assert strategy.move([]) == "C"
    assert client.call_count == 1


def test_llm_strategy_cache_persists_across_instances(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    client_a = StubClient(response="D")
    strategy_a = LLMStrategy(name="stub", system_prompt="prompt", client=client_a, cache=DiskCache(cache_path))
    strategy_a.move([])

    client_b = StubClient(response="C")  # would return "C" if actually called
    strategy_b = LLMStrategy(name="stub", system_prompt="prompt", client=client_b, cache=DiskCache(cache_path))

    assert strategy_b.move([]) == "D"
    assert client_b.call_count == 0
