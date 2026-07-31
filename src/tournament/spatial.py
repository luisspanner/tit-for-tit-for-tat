import random
from typing import Callable

from tournament.match import Match
from tournament.strategies.base import Strategy

# Fixed scan order for Moore-neighborhood offsets. Iteration order matters for
# deterministic tie-breaking: when multiple neighbors share the top payoff,
# the first one encountered in this order wins.
_NEIGHBOR_OFFSETS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1), (0, 1),
    (1, -1), (1, 0), (1, 1),
]

MATCH_ROUNDS = 10


class Grid:
    """A toroidal grid of strategies that plays Nowak-May spatial Prisoner's Dilemma.

    Each generation, every cell plays a short Match against each of its 8
    (wraparound) neighbors and sums the payoffs. Cells then simultaneously
    adopt the strategy of whichever cell in their neighborhood (including
    themselves) scored highest - ties are broken in favor of staying put,
    then by the fixed neighbor scan order above.
    """

    def __init__(
        self,
        size: int,
        strategy_factories: dict[str, Callable[[random.Random], Strategy]],
        seed: int | None = None,
        noise: float = 0.0,
    ) -> None:
        if size < 3:
            raise ValueError("Grid size must be >= 3 so Moore-neighborhood offsets don't wrap onto themselves")
        self.size = size
        self.strategy_factories = strategy_factories
        self.noise = noise
        self._rng = random.Random(seed)
        names = list(strategy_factories)
        self._cells: list[list[Strategy]] = [
            [strategy_factories[self._rng.choice(names)](self._rng) for _ in range(size)] for _ in range(size)
        ]

    def strategy_names(self) -> list[list[str]]:
        return [[cell.name for cell in row] for row in self._cells]

    def _neighbor_coords(self, row: int, col: int) -> list[tuple[int, int]]:
        return [((row + dr) % self.size, (col + dc) % self.size) for dr, dc in _NEIGHBOR_OFFSETS]

    def _payoff(self, row: int, col: int) -> int:
        cell = self._cells[row][col]
        total = 0
        for nr, nc in self._neighbor_coords(row, col):
            neighbor = self._cells[nr][nc]
            score, _, _ = Match(cell, neighbor, rounds=MATCH_ROUNDS, noise=self.noise, rng=self._rng).play()
            total += score
        return total

    def step(self) -> None:
        payoffs = [[self._payoff(row, col) for col in range(self.size)] for row in range(self.size)]

        next_cells: list[list[Strategy]] = [[None] * self.size for _ in range(self.size)]  # type: ignore[list-item]
        for row in range(self.size):
            for col in range(self.size):
                best_row, best_col = row, col
                best_payoff = payoffs[row][col]
                for nr, nc in self._neighbor_coords(row, col):
                    if payoffs[nr][nc] > best_payoff:
                        best_payoff = payoffs[nr][nc]
                        best_row, best_col = nr, nc
                winner_name = self._cells[best_row][best_col].name
                next_cells[row][col] = self.strategy_factories[winner_name](self._rng)

        self._cells = next_cells

    def strategy_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {name: 0 for name in self.strategy_factories}
        for row in self._cells:
            for cell in row:
                counts[cell.name] += 1
        return counts
