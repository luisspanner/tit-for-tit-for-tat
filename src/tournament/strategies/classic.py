import random

from tournament.payoff import R, T, score_round
from tournament.strategies.base import Move


class TitForTat:
    name = "tit_for_tat"

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        if not history:
            return "C"
        _, opponent_last = history[-1]
        return opponent_last


class AlwaysDefect:
    name = "always_defect"

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        return "D"


class AlwaysCooperate:
    name = "always_cooperate"

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        return "C"


class GrimTrigger:
    name = "grim_trigger"

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        if any(opponent_move == "D" for _, opponent_move in history):
            return "D"
        return "C"


class Pavlov:
    """Win-stay, lose-shift: repeat the last move after a good outcome (R or T), switch after a bad one (P or S)."""

    name = "pavlov"

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        if not history:
            return "C"
        my_last, opponent_last = history[-1]
        my_payoff, _ = score_round(my_last, opponent_last)
        won = my_payoff in (R, T)
        if won:
            return my_last
        return "D" if my_last == "C" else "C"


class RandomStrategy:
    name = "random"

    def __init__(self, p_cooperate: float = 0.5, seed: int | None = None) -> None:
        self.p_cooperate = p_cooperate
        self._rng = random.Random(seed)

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        return "C" if self._rng.random() < self.p_cooperate else "D"
