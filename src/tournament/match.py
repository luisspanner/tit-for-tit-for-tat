import random
from typing import Callable

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
        on_round: Callable[[int, Move, Move, str | None, str | None], None] | None = None,
    ) -> None:
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.rounds = rounds
        self.noise = noise
        self._rng = rng if rng is not None else random.Random()
        self.on_round = on_round

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
            # Captured right after move() returns, before any noise flip - this is
            # the strategy's reasoning for its *intended* move. If noise later flips
            # the executed move, the reasoning still describes the original intent,
            # not necessarily what actually got played. Dormant in practice: every
            # current LLM-involving run path uses noise=0.0.
            reason_a = getattr(self.strategy_a, "last_reasoning", None)
            intended_b = self.strategy_b.move(history_b, context)
            reason_b = getattr(self.strategy_b, "last_reasoning", None)

            move_a = self._execute(intended_a)
            move_b = self._execute(intended_b)

            round_score_a, round_score_b = score_round(move_a, move_b)
            score_a += round_score_a
            score_b += round_score_b

            history_a.append((move_a, move_b))
            history_b.append((move_b, move_a))

            if self.on_round is not None:
                self.on_round(round_index, move_a, move_b, reason_a, reason_b)

        return score_a, score_b, history_a
