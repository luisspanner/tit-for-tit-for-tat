from dataclasses import dataclass
from typing import Literal, Protocol

Move = Literal["C", "D"]


@dataclass(frozen=True)
class RoundContext:
    round_index: int
    total_rounds: int

    @property
    def is_last_round(self) -> bool:
        return self.round_index == self.total_rounds - 1


class Strategy(Protocol):
    name: str

    def move(self, history: list[tuple[Move, Move]], context: "RoundContext | None" = None) -> Move:
        """Decide the next move given (my_move, opponent_move) pairs so far, oldest first."""
        ...
