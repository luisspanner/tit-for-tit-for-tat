import random
from typing import Callable

from tournament.spatial import Grid
from tournament.strategies.base import Strategy
from tournament.tournament import Tournament


def sweep_round_robin(
    build_strategies: Callable[[], list[Strategy]],
    rounds: int,
    noise_levels: list[float],
    seed: int | None = None,
) -> dict[float, list[dict]]:
    """Run a fresh round-robin Tournament at each noise level, returning standings per level.

    `build_strategies` is called once per noise level (not a shared list) so that
    strategies with internal RNG state (RandomStrategy, GenerousTitForTat, Joss)
    start fresh each time rather than carrying consumed randomness over between levels.
    """
    results = {}
    for noise in noise_levels:
        strategies = build_strategies()
        tournament = Tournament(strategies, rounds=rounds, noise=noise, seed=seed)
        match_results = tournament.play()
        results[noise] = tournament.standings(match_results)
    return results


def sweep_spatial(
    size: int,
    strategy_factories: dict[str, Callable[[random.Random], Strategy]],
    generations: int,
    noise_levels: list[float],
    seed: int | None = None,
) -> dict[float, dict[str, int]]:
    """Run a fresh spatial Grid at each noise level, returning final strategy counts per level."""
    results = {}
    for noise in noise_levels:
        grid = Grid(size=size, strategy_factories=strategy_factories, seed=seed, noise=noise)
        for _ in range(generations):
            grid.step()
        results[noise] = grid.strategy_counts()
    return results
