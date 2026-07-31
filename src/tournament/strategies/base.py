from typing import Literal, Protocol

Move = Literal["C", "D"]


class Strategy(Protocol):
    name: str

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        """Decide the next move given (my_move, opponent_move) pairs so far, oldest first."""
        ...
