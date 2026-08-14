import random
from typing import Callable

from tournament.match import Match
from tournament.strategies.base import Move, Strategy


class Tournament:
    """Round-robin across a list of strategies, including each strategy against itself."""

    def __init__(
        self,
        strategies: list[Strategy],
        rounds: int = 100,
        noise: float = 0.0,
        seed: int | None = None,
    ) -> None:
        self.strategies = strategies
        self.rounds = rounds
        self.noise = noise
        self._rng = random.Random(seed)

    def play(
        self,
        on_match_start: Callable[[str, str, str | None, str | None], None] | None = None,
        on_round: Callable[[str, str, int, Move, Move, str | None, str | None], None] | None = None,
        on_match_end: Callable[[str, str, dict], None] | None = None,
        on_match_error: Callable[[str, str, Exception], None] | None = None,
    ) -> list[dict]:
        results = []
        for i, strategy_a in enumerate(self.strategies):
            for strategy_b in self.strategies[i:]:
                model_a = getattr(strategy_a, "model_name", None)
                model_b = getattr(strategy_b, "model_name", None)

                if on_match_start is not None:
                    on_match_start(strategy_a.name, strategy_b.name, model_a, model_b)

                match_on_round = None
                if on_round is not None:
                    match_on_round = (
                        lambda ri, ma, mb, ra, rb, a=strategy_a.name, b=strategy_b.name: on_round(
                            a, b, ri, ma, mb, ra, rb
                        )
                    )

                match = Match(
                    strategy_a,
                    strategy_b,
                    rounds=self.rounds,
                    noise=self.noise,
                    rng=self._rng,
                    on_round=match_on_round,
                )

                if on_match_error is not None:
                    try:
                        score_a, score_b, _ = match.play()
                    except Exception as exc:
                        on_match_error(strategy_a.name, strategy_b.name, exc)
                        continue
                else:
                    score_a, score_b, _ = match.play()

                result = {
                    "strategy_a": strategy_a.name,
                    "strategy_b": strategy_b.name,
                    "rounds": self.rounds,
                    "score_a": score_a,
                    "score_b": score_b,
                    "model_a": model_a,
                    "model_b": model_b,
                }
                results.append(result)

                if on_match_end is not None:
                    on_match_end(strategy_a.name, strategy_b.name, result)
        return results

    def standings(self, results: list[dict]) -> list[dict]:
        totals = {strategy.name: 0 for strategy in self.strategies}
        for result in results:
            totals[result["strategy_a"]] += result["score_a"]
            totals[result["strategy_b"]] += result["score_b"]

        rows = [{"strategy": name, "total_score": score} for name, score in totals.items()]
        return sorted(rows, key=lambda row: row["total_score"], reverse=True)
