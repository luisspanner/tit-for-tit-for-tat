from tournament.experiments import sweep_round_robin, sweep_spatial
from tournament.strategies.classic import AlwaysCooperate, AlwaysDefect


def test_sweep_round_robin_no_noise_matches_existing_tournament_result() -> None:
    def build():
        return [AlwaysCooperate(), AlwaysDefect()]

    results = sweep_round_robin(build, rounds=2, noise_levels=[0.0], seed=1)
    totals = {row["strategy"]: row["total_score"] for row in results[0.0]}

    # Same hand-computed result as test_tournament.py's noise-free case.
    assert totals["always_cooperate"] == 12
    assert totals["always_defect"] == 14


def test_sweep_round_robin_full_noise_inverts_the_result() -> None:
    def build():
        return [AlwaysCooperate(), AlwaysDefect()]

    results = sweep_round_robin(build, rounds=2, noise_levels=[1.0], seed=1)
    totals = {row["strategy"]: row["total_score"] for row in results[1.0]}

    # noise=1.0 flips every move, so the whole tournament plays out with the
    # two strategies' roles swapped - exactly the inverse of the noise=0.0 totals.
    assert totals["always_cooperate"] == 14
    assert totals["always_defect"] == 12


def test_sweep_round_robin_rebuilds_fresh_strategies_per_noise_level() -> None:
    call_count = 0

    def build():
        nonlocal call_count
        call_count += 1
        return [AlwaysCooperate(), AlwaysDefect()]

    sweep_round_robin(build, rounds=2, noise_levels=[0.0, 0.1, 0.2], seed=1)
    assert call_count == 3


def test_sweep_spatial_uniform_grid_is_a_fixed_point_at_every_noise_level() -> None:
    # A grid seeded with only one strategy type stays uniform (a fixed point)
    # at every noise level, since every cell always scores identically to its
    # neighbors regardless of what noise does to the actually-played moves.
    factories = {"always_cooperate": lambda rng: AlwaysCooperate()}
    results = sweep_spatial(size=3, strategy_factories=factories, generations=3, noise_levels=[0.0, 1.0], seed=0)

    assert results[0.0] == {"always_cooperate": 9}
    assert results[1.0] == {"always_cooperate": 9}


def test_sweep_spatial_noise_actually_changes_the_outcome() -> None:
    # At this seed, always_defect wins the noise-free 3x3 grid outright; at
    # noise=1.0 every move flips, which swaps the two strategies' effective
    # roles in every match, so always_cooperate wins instead - proof `noise`
    # genuinely reaches the underlying Grid/Match, not just a no-op parameter.
    factories = {
        "always_cooperate": lambda rng: AlwaysCooperate(),
        "always_defect": lambda rng: AlwaysDefect(),
    }
    results = sweep_spatial(size=3, strategy_factories=factories, generations=1, noise_levels=[0.0, 1.0], seed=3)

    assert results[0.0] == {"always_cooperate": 0, "always_defect": 9}
    assert results[1.0] == {"always_cooperate": 9, "always_defect": 0}
