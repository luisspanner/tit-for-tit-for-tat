from tournament.match import Match
from tournament.strategies.base import Strategy


class Tournament:
    """Round-robin across a list of strategies, including each strategy against itself."""

    def __init__(self, strategies: list[Strategy], rounds: int = 100) -> None:
        self.strategies = strategies
        self.rounds = rounds

    def play(self) -> list[dict]:
        results = []
        for i, strategy_a in enumerate(self.strategies):
            for strategy_b in self.strategies[i:]:
                match = Match(strategy_a, strategy_b, rounds=self.rounds)
                score_a, score_b, _ = match.play()
                results.append(
                    {
                        "strategy_a": strategy_a.name,
                        "strategy_b": strategy_b.name,
                        "rounds": self.rounds,
                        "score_a": score_a,
                        "score_b": score_b,
                    }
                )
        return results

    def standings(self, results: list[dict]) -> list[dict]:
        totals = {strategy.name: 0 for strategy in self.strategies}
        for result in results:
            totals[result["strategy_a"]] += result["score_a"]
            totals[result["strategy_b"]] += result["score_b"]

        rows = [{"strategy": name, "total_score": score} for name, score in totals.items()]
        return sorted(rows, key=lambda row: row["total_score"], reverse=True)
