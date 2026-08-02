import random

from tournament.match import Match
from tournament.strategies.base import Strategy


class EcologicalTournament:
    """Axelrod-style replicator dynamics: population shares evolve proportional
    to average payoff against the *whole* mixed population, not fixed neighbors.
    """

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
        # Two fixed strategies' expected payoff against each other doesn't change
        # generation to generation - only the population weighting does - so this
        # is computed once up front rather than re-simulated every generation.
        self._payoff_matrix = self._compute_pairwise_average_payoffs()

    def _compute_pairwise_average_payoffs(self) -> dict[tuple[str, str], float]:
        matrix = {}
        for strategy_a in self.strategies:
            for strategy_b in self.strategies:
                score_a, _, _ = Match(strategy_a, strategy_b, rounds=self.rounds, noise=self.noise, rng=self._rng).play()
                matrix[(strategy_a.name, strategy_b.name)] = score_a / self.rounds
        return matrix

    def run(self, generations: int, initial_shares: dict[str, float] | None = None) -> list[dict[str, float]]:
        names = [strategy.name for strategy in self.strategies]
        shares = dict(initial_shares) if initial_shares is not None else {name: 1 / len(names) for name in names}
        history = [dict(shares)]

        for _ in range(generations):
            fitness = {
                name: sum(shares[opponent] * self._payoff_matrix[(name, opponent)] for opponent in names)
                for name in names
            }
            average_fitness = sum(shares[name] * fitness[name] for name in names)

            shares = {name: shares[name] * fitness[name] / average_fitness for name in names}
            total = sum(shares.values())
            shares = {name: value / total for name, value in shares.items()}  # guard against float drift

            history.append(dict(shares))

        return history
