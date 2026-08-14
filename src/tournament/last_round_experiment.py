from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from tournament.experiment_stats import DEFAULT_OPPONENT_FACTORIES, two_proportion_z, two_tailed_p_value
from tournament.llm_roster import build_llm_strategies
from tournament.match import Match
from tournament.strategies.base import Strategy
from tournament.strategies.llm import LLMStrategy


@dataclass
class ConditionResult:
    """Aggregated outcome of running one LLM strategy under one condition
    (told/untold) against every reference opponent, repeated `repeats` times."""

    cooperation_by_round: list[float | None]
    last_round_defections: int
    last_round_total: int
    raw: list[dict] = field(default_factory=list)

    @property
    def last_round_defect_rate(self) -> float | None:
        if self.last_round_total == 0:
            return None
        return self.last_round_defections / self.last_round_total


def _fresh_uncached_strategy(base: LLMStrategy, announce_last_round: bool) -> LLMStrategy:
    """A copy of `base` sharing its LLMClient but with caching disabled, so
    repeated matches produce independent live calls instead of replaying the
    same cached response every repeat."""
    return LLMStrategy(
        name=base.name,
        system_prompt=base.system_prompt,
        client=base.client,
        cache=None,
        model_name=base.model_name,
        announce_last_round=announce_last_round,
    )


def _run_condition(
    base_strategy: LLMStrategy,
    announce_last_round: bool,
    opponent_factories: list[Callable[[], Strategy]],
    rounds: int,
    repeats: int,
    on_repeat_start: Callable[[str, str, int], None] | None = None,
    on_repeat_end: Callable[[str, str, int, list[str]], None] | None = None,
) -> ConditionResult:
    cooperations_by_round: list[list[bool]] = [[] for _ in range(rounds)]
    last_round_defections = 0
    last_round_total = 0
    raw: list[dict] = []

    for opponent_factory in opponent_factories:
        for repeat in range(repeats):
            opponent = opponent_factory()
            if on_repeat_start is not None:
                on_repeat_start(base_strategy.model_name or "", opponent.name, repeat)

            strategy = _fresh_uncached_strategy(base_strategy, announce_last_round)
            _, _, history = Match(strategy, opponent, rounds=rounds).play()

            for round_index, (mine, _theirs) in enumerate(history):
                cooperations_by_round[round_index].append(mine == "C")

            last_round_total += 1
            if history[-1][0] == "D":
                last_round_defections += 1

            moves = [mine for mine, _theirs in history]
            raw.append({"opponent": opponent.name, "repeat": repeat, "moves": moves})

            if on_repeat_end is not None:
                on_repeat_end(base_strategy.model_name or "", opponent.name, repeat, moves)

    cooperation_by_round = [
        sum(values) / len(values) if values else None for values in cooperations_by_round
    ]
    return ConditionResult(
        cooperation_by_round=cooperation_by_round,
        last_round_defections=last_round_defections,
        last_round_total=last_round_total,
        raw=raw,
    )


def run_last_round_experiment(
    system_prompt: str,
    cache_dir: Path,
    rounds: int = 20,
    repeats: int = 3,
    opponent_factories: list[Callable[[], Strategy]] | None = None,
    models: list[str] | None = None,
    on_repeat_start: Callable[[str, str, int], None] | None = None,
    on_repeat_end: Callable[[str, str, int, list[str]], None] | None = None,
    on_model_done: Callable[[str, dict], None] | None = None,
) -> dict:
    """For every configured LLM model (or, if `models` is given, only those
    whose model_name is in it), plays it under two conditions - 'told' (the
    standard last-round announcement) and 'untold' (the notice withheld even
    on the actual last round) - against a fixed panel of nice-opener
    reference opponents, and compares last-round defection rates between the
    two conditions."""
    opponent_factories = opponent_factories if opponent_factories is not None else DEFAULT_OPPONENT_FACTORIES

    told_roster = build_llm_strategies(system_prompt, cache_dir, announce_last_round=True)
    if models is not None:
        told_roster = [s for s in told_roster if s.model_name in models]
    untold_roster = build_llm_strategies(system_prompt, cache_dir, announce_last_round=False)
    untold_by_model = {s.model_name: s for s in untold_roster}

    summary: dict[str, dict] = {}
    for told_strategy in told_roster:
        untold_strategy = untold_by_model.get(told_strategy.model_name)
        if untold_strategy is None:
            continue

        told_result = _run_condition(
            told_strategy, True, opponent_factories, rounds, repeats, on_repeat_start, on_repeat_end
        )
        untold_result = _run_condition(
            untold_strategy, False, opponent_factories, rounds, repeats, on_repeat_start, on_repeat_end
        )

        z = two_proportion_z(
            told_result.last_round_defections,
            told_result.last_round_total,
            untold_result.last_round_defections,
            untold_result.last_round_total,
        )

        result = {
            "told": {
                "last_round_defect_rate": told_result.last_round_defect_rate,
                "last_round_defections": told_result.last_round_defections,
                "last_round_total": told_result.last_round_total,
                "cooperation_by_round": told_result.cooperation_by_round,
                "raw": told_result.raw,
            },
            "untold": {
                "last_round_defect_rate": untold_result.last_round_defect_rate,
                "last_round_defections": untold_result.last_round_defections,
                "last_round_total": untold_result.last_round_total,
                "cooperation_by_round": untold_result.cooperation_by_round,
                "raw": untold_result.raw,
            },
            "z_score": z,
            "p_value": two_tailed_p_value(z) if z is not None else None,
        }
        summary[told_strategy.model_name] = result

        if on_model_done is not None:
            on_model_done(told_strategy.model_name or "", result)

    return summary
