import random

from tournament.payoff import R, T, score_round
from tournament.strategies.base import Move, RoundContext


class TitForTat:
    name = "tit_for_tat"

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        if not history:
            return "C"
        _, opponent_last = history[-1]
        return opponent_last


class AlwaysDefect:
    name = "always_defect"

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        return "D"


class AlwaysCooperate:
    name = "always_cooperate"

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        return "C"


class GrimTrigger:
    name = "grim_trigger"

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        if any(opponent_move == "D" for _, opponent_move in history):
            return "D"
        return "C"


class Pavlov:
    """Win-stay, lose-shift: repeat the last move after a good outcome (R or T), switch after a bad one (P or S)."""

    name = "pavlov"

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
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

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        return "C" if self._rng.random() < self.p_cooperate else "D"


class GenerousTitForTat:
    """Tit-for-tat that forgives a defection with probability `generosity` instead of always retaliating."""

    name = "generous_tit_for_tat"

    def __init__(self, generosity: float = 0.1, seed: int | None = None) -> None:
        self.generosity = generosity
        self._rng = random.Random(seed)

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        if not history:
            return "C"
        _, opponent_last = history[-1]
        if opponent_last == "D" and self._rng.random() < self.generosity:
            return "C"
        return opponent_last


class Joss:
    """Tit-for-tat that opportunistically defects unprovoked with probability `defection_probability`."""

    name = "joss"

    def __init__(self, defection_probability: float = 0.1, seed: int | None = None) -> None:
        self.defection_probability = defection_probability
        self._rng = random.Random(seed)

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        base = "C" if not history else history[-1][1]
        if base == "C" and self._rng.random() < self.defection_probability:
            return "D"
        return base


class EndgameDefector:
    """Tit-for-tat that unconditionally defects on the last round, regardless of history."""

    name = "endgame_defector"

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        if context is not None and context.is_last_round:
            return "D"
        if not history:
            return "C"
        _, opponent_last = history[-1]
        return opponent_last
