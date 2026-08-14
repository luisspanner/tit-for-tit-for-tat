from tournament.strategies.classic import AlwaysCooperate, AlwaysDefect, TitForTat
from tournament.strategies.llm import LLMStrategy
from tournament.tournament import Tournament


class StubClient:
    def complete(self, system_prompt: str, user_message: str) -> str:
        return "C"


class FailingClient:
    def complete(self, system_prompt: str, user_message: str) -> str:
        raise RuntimeError("boom")


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


def test_play_records_model_name_for_llm_strategies_and_none_for_classic() -> None:
    llm_strategy = LLMStrategy(name="llm_stub", system_prompt="p", client=StubClient(), model_name="model-x")
    strategies = [AlwaysCooperate(), llm_strategy]
    tournament = Tournament(strategies, rounds=2)
    results = tournament.play()

    classic_self_match = next(
        r for r in results if r["strategy_a"] == "always_cooperate" and r["strategy_b"] == "always_cooperate"
    )
    assert classic_self_match["model_a"] is None
    assert classic_self_match["model_b"] is None

    cross_match = next(r for r in results if r["strategy_b"] == "llm_stub")
    assert cross_match["model_a"] is None
    assert cross_match["model_b"] == "model-x"


def test_callbacks_default_to_none_and_do_not_change_results() -> None:
    strategies = [AlwaysCooperate(), AlwaysDefect()]
    tournament = Tournament(strategies, rounds=2)

    assert tournament.play() == tournament.play()


def test_on_match_start_and_on_match_end_fire_for_every_pair() -> None:
    strategies = [AlwaysCooperate(), AlwaysDefect()]
    tournament = Tournament(strategies, rounds=2)
    starts = []
    ends = []
    results = tournament.play(
        on_match_start=lambda a, b, ma, mb: starts.append((a, b, ma, mb)),
        on_match_end=lambda a, b, result: ends.append((a, b, result)),
    )

    assert len(starts) == len(ends) == len(results) == 3
    assert starts[0] == ("always_cooperate", "always_cooperate", None, None)
    assert ends[0][2]["score_a"] == results[0]["score_a"]


def test_on_round_forwards_pair_names_alongside_round_data() -> None:
    strategies = [AlwaysCooperate(), AlwaysDefect()]
    tournament = Tournament(strategies, rounds=2)
    rounds_seen = []
    tournament.play(on_round=lambda a, b, ri, ma, mb, ra, rb: rounds_seen.append((a, b, ri, ma, mb)))

    # 3 pairs (self, self, cross) * 2 rounds each = 6 round events.
    assert len(rounds_seen) == 6
    assert rounds_seen[0] == ("always_cooperate", "always_cooperate", 0, "C", "C")


def test_on_match_error_skips_failing_pair_and_continues() -> None:
    failing_llm = LLMStrategy(name="llm_fails", system_prompt="p", client=FailingClient())
    strategies = [AlwaysCooperate(), failing_llm]
    tournament = Tournament(strategies, rounds=2)
    errors = []
    results = tournament.play(on_match_error=lambda a, b, exc: errors.append((a, b, str(exc))))

    pairs = {(r["strategy_a"], r["strategy_b"]) for r in results}
    assert ("always_cooperate", "always_cooperate") in pairs
    assert not any("llm_fails" in pair for pair in pairs)
    assert len(errors) == 2  # llm_fails vs always_cooperate, and llm_fails vs itself
    assert all(exc == "boom" for _, _, exc in errors)


def test_without_on_match_error_an_exception_still_propagates() -> None:
    failing_llm = LLMStrategy(name="llm_fails", system_prompt="p", client=FailingClient())
    tournament = Tournament([failing_llm], rounds=2)

    try:
        tournament.play()
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected RuntimeError to propagate")


def test_noise_one_forwarded_to_every_match_flips_all_moves() -> None:
    strategies = [AlwaysCooperate(), AlwaysCooperate()]
    tournament = Tournament(strategies, rounds=3, noise=1.0, seed=1)
    results = tournament.play()

    # Every AlwaysCooperate move actually gets flipped to D under noise=1.0,
    # so every match scores as mutual defection: P=1/round * 3 rounds = 3.
    assert all(r["score_a"] == 3 and r["score_b"] == 3 for r in results)
