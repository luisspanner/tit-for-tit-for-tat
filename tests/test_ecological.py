import pytest

from tournament.ecological import EcologicalTournament
from tournament.strategies.classic import AlwaysCooperate, AlwaysDefect


def test_payoff_matrix_hand_computed_with_single_round() -> None:
    eco = EcologicalTournament([AlwaysCooperate(), AlwaysDefect()], rounds=1, seed=0)

    assert eco._payoff_matrix == {
        ("always_cooperate", "always_cooperate"): 3.0,  # mutual C -> R
        ("always_cooperate", "always_defect"): 0.0,  # C vs D -> S
        ("always_defect", "always_cooperate"): 5.0,  # D vs C -> T
        ("always_defect", "always_defect"): 1.0,  # mutual D -> P
    }


def test_run_single_generation_hand_computed_replicator_update() -> None:
    eco = EcologicalTournament([AlwaysCooperate(), AlwaysDefect()], rounds=1, seed=0)
    history = eco.run(generations=1)

    assert history[0] == {"always_cooperate": 0.5, "always_defect": 0.5}
    # fitness(AC) = 0.5*3 + 0.5*0 = 1.5; fitness(AD) = 0.5*5 + 0.5*1 = 3.0
    # avg_fitness = 0.5*1.5 + 0.5*3.0 = 2.25
    # new_share(AC) = 0.5*1.5/2.25 = 1/3; new_share(AD) = 0.5*3.0/2.25 = 2/3
    assert history[1]["always_cooperate"] == pytest.approx(1 / 3)
    assert history[1]["always_defect"] == pytest.approx(2 / 3)


def test_monomorphic_population_is_a_fixed_point() -> None:
    eco = EcologicalTournament([AlwaysCooperate(), AlwaysDefect()], rounds=10, seed=0)
    history = eco.run(generations=5, initial_shares={"always_cooperate": 1.0, "always_defect": 0.0})

    assert all(gen["always_cooperate"] == pytest.approx(1.0) for gen in history)
    assert all(gen["always_defect"] == pytest.approx(0.0) for gen in history)


def test_shares_always_sum_to_one() -> None:
    eco = EcologicalTournament([AlwaysCooperate(), AlwaysDefect()], rounds=10, seed=0)
    history = eco.run(generations=20)

    assert all(sum(gen.values()) == pytest.approx(1.0) for gen in history)
