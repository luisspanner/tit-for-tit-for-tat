import random

from tournament.payoff import score_round
from tournament.strategies.base import Move, RoundContext, Strategy


def _flip(move: Move) -> Move:
    return "D" if move == "C" else "C"


class Match:
    def __init__(
        self,
        strategy_a: Strategy,
        strategy_b: Strategy,
        rounds: int = 100,
        noise: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.rounds = rounds
        self.noise = noise
        self._rng = rng if rng is not None else random.Random()

    def _execute(self, intended: Move) -> Move:
        if self._rng.random() < self.noise:
            return _flip(intended)
        return intended

    def play(self) -> tuple[int, int, list[tuple[Move, Move]]]:
        history_a: list[tuple[Move, Move]] = []
        history_b: list[tuple[Move, Move]] = []
        score_a = 0
        score_b = 0

        for round_index in range(self.rounds):
            context = RoundContext(round_index=round_index, total_rounds=self.rounds)

            intended_a = self.strategy_a.move(history_a, context)
            intended_b = self.strategy_b.move(history_b, context)

            move_a = self._execute(intended_a)
            move_b = self._execute(intended_b)

            round_score_a, round_score_b = score_round(move_a, move_b)
            score_a += round_score_a
            score_b += round_score_b

            history_a.append((move_a, move_b))
            history_b.append((move_b, move_a))

        return score_a, score_b, history_a
