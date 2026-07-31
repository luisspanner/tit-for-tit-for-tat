import pytest

from tournament.payoff import P
from tournament.spatial import MATCH_ROUNDS, Grid
from tournament.strategies.classic import AlwaysCooperate, AlwaysDefect

FACTORIES = {
    "always_cooperate": lambda rng: AlwaysCooperate(),
    "always_defect": lambda rng: AlwaysDefect(),
}


def test_grid_rejects_too_small_size() -> None:
    with pytest.raises(ValueError):
        Grid(size=2, strategy_factories=FACTORIES, seed=0)


def test_neighbor_coords_on_3x3_torus_are_all_distinct_and_exclude_self() -> None:
    grid = Grid(size=3, strategy_factories=FACTORIES, seed=0)
    neighbors = grid._neighbor_coords(0, 0)
    assert len(neighbors) == 8
    assert len(set(neighbors)) == 8
    assert (0, 0) not in neighbors
    # On a 3x3 torus every other cell is a neighbor of (0, 0).
    all_cells = {(r, c) for r in range(3) for c in range(3)}
    assert set(neighbors) == all_cells - {(0, 0)}


def test_strategy_names_matches_grid_size() -> None:
    grid = Grid(size=3, strategy_factories=FACTORIES, seed=0)
    names = grid.strategy_names()
    assert len(names) == 3
    assert all(len(row) == 3 for row in names)
    assert all(name in FACTORIES for row in names for name in row)


def test_isolated_cooperate_cell_surrounded_by_defectors_converts_to_defect() -> None:
    # 3x3 grid: every cell always_defect except the center, which is always_cooperate.
    # Center's payoff: 8 neighbors x 10 rounds x S(0) = 0.
    # A corner defector's payoff includes at least one match against the cooperator
    # (T=5/round) and the rest against fellow defectors (P=1/round) - strictly higher
    # than the center's 0. So the center must switch to always_defect next generation.
    grid = Grid(size=3, strategy_factories=FACTORIES, seed=0)
    for row in range(3):
        for col in range(3):
            grid._cells[row][col] = AlwaysDefect()
    grid._cells[1][1] = AlwaysCooperate()

    grid.step()

    assert grid.strategy_names()[1][1] == "always_defect"


def test_uniform_grid_is_a_fixed_point() -> None:
    grid = Grid(size=3, strategy_factories=FACTORIES, seed=0)
    for row in range(3):
        for col in range(3):
            grid._cells[row][col] = AlwaysCooperate()

    grid.step()

    assert all(name == "always_cooperate" for row in grid.strategy_names() for name in row)


def test_strategy_counts_sum_to_grid_area() -> None:
    grid = Grid(size=4, strategy_factories=FACTORIES, seed=1)
    counts = grid.strategy_counts()
    assert sum(counts.values()) == 16
    assert set(counts) == set(FACTORIES)


def test_noise_forwarded_to_internal_matches() -> None:
    # Uniform always_cooperate grid: under noise=1.0 every recorded move flips
    # to D, so every cell's payoff becomes 8 neighbors x MATCH_ROUNDS x P
    # instead of the noise-free R.
    grid = Grid(size=3, strategy_factories=FACTORIES, seed=0, noise=1.0)
    for row in range(3):
        for col in range(3):
            grid._cells[row][col] = AlwaysCooperate()

    assert grid._payoff(0, 0) == 8 * MATCH_ROUNDS * P
