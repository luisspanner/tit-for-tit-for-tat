from pathlib import Path

import pytest

from tournament.cache import DiskCache
from tournament.strategies.base import RoundContext
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


def test_render_history_mentions_last_round_only_when_context_says_so() -> None:
    not_last = RoundContext(round_index=0, total_rounds=5)
    last = RoundContext(round_index=4, total_rounds=5)

    assert "final round" not in render_history([], context=None).lower()
    assert "final round" not in render_history([], context=not_last).lower()
    assert "final round" in render_history([], context=last).lower()


def test_llm_strategy_passes_context_through_to_the_rendered_prompt() -> None:
    client = StubClient(response="D")
    strategy = LLMStrategy(name="stub", system_prompt="be ruthless", client=client)

    strategy.move([], context=RoundContext(round_index=9, total_rounds=10))

    assert "final round" in client.last_user_message.lower()


def test_llm_strategy_cache_key_differs_by_last_round_flag(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    not_last_client = StubClient(response="C")
    strategy = LLMStrategy(
        name="stub", system_prompt="prompt", client=not_last_client, cache=DiskCache(cache_path)
    )
    strategy.move([], context=RoundContext(round_index=0, total_rounds=10))
    assert not_last_client.call_count == 1

    last_client = StubClient(response="D")
    strategy_last = LLMStrategy(
        name="stub", system_prompt="prompt", client=last_client, cache=DiskCache(cache_path)
    )
    # Same history, but is_last_round differs - must NOT be served from the
    # non-last-round cache entry, since the rendered prompt actually differs.
    assert strategy_last.move([], context=RoundContext(round_index=9, total_rounds=10)) == "D"
    assert last_client.call_count == 1


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
