from tournament.strategies.classic import AlwaysCooperate, AlwaysDefect, TitForTat
from tournament.tournament import Tournament


def test_play_includes_every_pair_including_self_play() -> None:
    strategies = [AlwaysCooperate(), AlwaysDefect()]
    tournament = Tournament(strategies, rounds=2)
    results = tournament.play()

    pairs = {(r["strategy_a"], r["strategy_b"]) for r in results}
    assert pairs == {
        ("always_cooperate", "always_cooperate"),
        ("always_cooperate", "always_defect"),
        ("always_defect", "always_defect"),
    }


def test_play_hand_computed_scores_for_two_rounds() -> None:
    # AlwaysCooperate vs AlwaysDefect, 2 rounds: every round is (C, D) -> scores (S=0, T=5) each round.
    strategies = [AlwaysCooperate(), AlwaysDefect()]
    tournament = Tournament(strategies, rounds=2)
    results = tournament.play()

    cross_match = next(r for r in results if r["strategy_a"] == "always_cooperate" and r["strategy_b"] == "always_defect")
    assert cross_match["score_a"] == 0
    assert cross_match["score_b"] == 10

    self_match = next(r for r in results if r["strategy_a"] == "always_defect" and r["strategy_b"] == "always_defect")
    assert self_match["score_a"] == 2
    assert self_match["score_b"] == 2


def test_standings_aggregates_total_score_across_all_matches() -> None:
    strategies = [AlwaysCooperate(), AlwaysDefect()]
    tournament = Tournament(strategies, rounds=2)
    results = tournament.play()
    standings = tournament.standings(results)

    totals = {row["strategy"]: row["total_score"] for row in standings}
    # always_cooperate: 6 + 6 (both sides of the self-match vs itself, R=3/round * 2 each)
    # + 0 (vs always_defect, S=0/round) = 12
    assert totals["always_cooperate"] == 12
    # always_defect: 10 (vs always_cooperate, T=5/round * 2) + 2 + 2 (both sides of the
    # self-match vs itself, P=1/round * 2 each) = 14
    assert totals["always_defect"] == 14


def test_standings_sorted_descending_by_total_score() -> None:
    strategies = [AlwaysCooperate(), AlwaysDefect(), TitForTat()]
    tournament = Tournament(strategies, rounds=10)
    results = tournament.play()
    standings = tournament.standings(results)

    scores = [row["total_score"] for row in standings]
    assert scores == sorted(scores, reverse=True)


def test_noise_one_forwarded_to_every_match_flips_all_moves() -> None:
    strategies = [AlwaysCooperate(), AlwaysCooperate()]
    tournament = Tournament(strategies, rounds=3, noise=1.0, seed=1)
    results = tournament.play()

    # Every AlwaysCooperate move actually gets flipped to D under noise=1.0,
    # so every match scores as mutual defection: P=1/round * 3 rounds = 3.
    assert all(r["score_a"] == 3 and r["score_b"] == 3 for r in results)
