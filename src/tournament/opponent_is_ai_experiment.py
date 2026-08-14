from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from tournament.experiment_stats import DEFAULT_OPPONENT_FACTORIES, two_proportion_z, two_tailed_p_value
from tournament.llm_roster import build_llm_strategies
from tournament.match import Match
from tournament.strategies.base import Strategy
from tournament.strategies.llm import LLMStrategy


@dataclass
class OpponentIsAiConditionResult:
    """Aggregated outcome of running one LLM strategy under one condition
    (baseline/ai_revealed) against every reference opponent, repeated
    `repeats` times. Unlike the last-round experiment, there is no single
    'critical round' here - the outcome metric is the aggregate cooperation
    rate across every move played under the condition."""

    cooperation_rate: float | None
    total_moves: int
    cooperations: int
    raw: list[dict] = field(default_factory=list)


def _fresh_uncached_strategy(base: LLMStrategy) -> LLMStrategy:
    """A copy of `base` sharing its LLMClient but with caching disabled, so
    repeated matches produce independent live calls instead of replaying the
    same cached response every repeat."""
    return LLMStrategy(
        name=base.name,
        system_prompt=base.system_prompt,
        client=base.client,
        cache=None,
        model_name=base.model_name,
    )


def _run_condition(
    base_strategy: LLMStrategy,
    opponent_factories: list[Callable[[], Strategy]],
    rounds: int,
    repeats: int,
    on_repeat_start: Callable[[str, str, int], None] | None = None,
    on_repeat_end: Callable[[str, str, int, list[str]], None] | None = None,
) -> OpponentIsAiConditionResult:
    cooperations = 0
    total_moves = 0
    raw: list[dict] = []

    for opponent_factory in opponent_factories:
        for repeat in range(repeats):
            opponent = opponent_factory()
            if on_repeat_start is not None:
                on_repeat_start(base_strategy.model_name or "", opponent.name, repeat)

            strategy = _fresh_uncached_strategy(base_strategy)
            _, _, history = Match(strategy, opponent, rounds=rounds).play()
            moves = [mine for mine, _theirs in history]

            cooperations += sum(1 for m in moves if m == "C")
            total_moves += len(moves)
            raw.append({"opponent": opponent.name, "repeat": repeat, "moves": moves})

            if on_repeat_end is not None:
                on_repeat_end(base_strategy.model_name or "", opponent.name, repeat, moves)

    cooperation_rate = cooperations / total_moves if total_moves else None
    return OpponentIsAiConditionResult(
        cooperation_rate=cooperation_rate, total_moves=total_moves, cooperations=cooperations, raw=raw
    )


def run_opponent_is_ai_experiment(
    cache_dir: Path,
    prompts_dir: Path,
    rounds: int = 20,
    repeats: int = 5,
    opponent_factories: list[Callable[[], Strategy]] | None = None,
    on_repeat_start: Callable[[str, str, int], None] | None = None,
    on_repeat_end: Callable[[str, str, int, list[str]], None] | None = None,
    on_model_done: Callable[[str, dict], None] | None = None,
) -> dict:
    """For every configured LLM model, plays it under two conditions -
    'baseline' (standard prompt) and 'ai_revealed' (system prompt discloses
    the opponent is also an AI) - against a fixed panel of nice-opener
    reference opponents, and compares aggregate cooperation rates between
    the two conditions."""
    opponent_factories = opponent_factories if opponent_factories is not None else DEFAULT_OPPONENT_FACTORIES

    baseline_prompt = (prompts_dir / "baseline.txt").read_text()
    ai_reveal_prompt = (prompts_dir / "opponent_is_ai.txt").read_text()
    baseline_roster = build_llm_strategies(baseline_prompt, cache_dir)
    ai_reveal_roster = build_llm_strategies(ai_reveal_prompt, cache_dir)
    ai_reveal_by_model = {s.model_name: s for s in ai_reveal_roster}

    summary: dict[str, dict] = {}
    for baseline_strategy in baseline_roster:
        ai_strategy = ai_reveal_by_model.get(baseline_strategy.model_name)
        if ai_strategy is None:
            continue

        baseline_result = _run_condition(
            baseline_strategy, opponent_factories, rounds, repeats, on_repeat_start, on_repeat_end
        )
        ai_result = _run_condition(
            ai_strategy, opponent_factories, rounds, repeats, on_repeat_start, on_repeat_end
        )

        z = two_proportion_z(
            baseline_result.total_moves - baseline_result.cooperations,
            baseline_result.total_moves,
            ai_result.total_moves - ai_result.cooperations,
            ai_result.total_moves,
        )

        result = {
            "baseline": {
                "cooperation_rate": baseline_result.cooperation_rate,
                "total_moves": baseline_result.total_moves,
                "cooperations": baseline_result.cooperations,
                "raw": baseline_result.raw,
            },
            "ai_revealed": {
                "cooperation_rate": ai_result.cooperation_rate,
                "total_moves": ai_result.total_moves,
                "cooperations": ai_result.cooperations,
                "raw": ai_result.raw,
            },
            "z_score": z,
            "p_value": two_tailed_p_value(z) if z is not None else None,
        }
        summary[baseline_strategy.model_name] = result

        if on_model_done is not None:
            on_model_done(baseline_strategy.model_name or "", result)

    return summary
