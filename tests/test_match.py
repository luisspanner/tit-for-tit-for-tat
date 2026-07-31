import random

from tournament.match import Match
from tournament.strategies.base import RoundContext
from tournament.strategies.classic import AlwaysCooperate, AlwaysDefect, GrimTrigger, TitForTat


class ScriptedRandom:
    """A fake RNG that returns a fixed, exhausted-checkable sequence of floats."""

    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values)


class ContextSpy:
    name = "context_spy"

    def __init__(self) -> None:
        self.contexts_seen: list[RoundContext] = []

    def move(self, history, context=None):
        self.contexts_seen.append(context)
        return "C"


def test_tit_for_tat_vs_always_defect_known_outcome() -> None:
    # Round 1: TFT cooperates, AlwaysDefect defects -> TFT gets S=0, Defect gets T=5.
    # TFT then copies "D" for every remaining round -> mutual defection, P=1 each.
    rounds = 10
    match = Match(TitForTat(), AlwaysDefect(), rounds=rounds)
    score_tft, score_defect, history = match.play()

    assert history[0] == ("C", "D")
    assert all(move == ("D", "D") for move in history[1:])
    assert score_tft == 0 + (rounds - 1) * 1
    assert score_defect == 5 + (rounds - 1) * 1


def test_match_passes_round_context_with_correct_index_and_last_round_flag() -> None:
    spy_a = ContextSpy()
    spy_b = ContextSpy()
    Match(spy_a, spy_b, rounds=5).play()

    assert [c.round_index for c in spy_a.contexts_seen] == [0, 1, 2, 3, 4]
    assert all(c.total_rounds == 5 for c in spy_a.contexts_seen)
    assert [c.is_last_round for c in spy_a.contexts_seen] == [False, False, False, False, True]
    # Both strategies see the same context object each round.
    assert spy_a.contexts_seen == spy_b.contexts_seen


def test_noise_zero_is_a_no_op_matching_the_default() -> None:
    rounds = 10
    match = Match(TitForTat(), AlwaysDefect(), rounds=rounds, noise=0.0, rng=random.Random(123))
    score_tft, score_defect, history = match.play()

    assert history[0] == ("C", "D")
    assert all(move == ("D", "D") for move in history[1:])
    assert score_tft == 0 + (rounds - 1) * 1
    assert score_defect == 5 + (rounds - 1) * 1


def test_noise_one_flips_every_recorded_move() -> None:
    match = Match(AlwaysCooperate(), AlwaysCooperate(), rounds=10, noise=1.0, rng=random.Random(1))
    _, _, history = match.play()

    assert all(move == ("D", "D") for move in history)


def test_grim_trigger_locks_into_permanent_defection_after_one_accidental_flip() -> None:
    # A single forced flip of player A's move at round index 2 (the 5th of 12
    # random() calls: 2 per round x rounds 0 and 1, then A's call in round 2).
    values = [0.9] * 4 + [0.1] + [0.9] * 20
    rng = ScriptedRandom(values)

    _, _, history = Match(GrimTrigger(), GrimTrigger(), rounds=10, noise=0.5, rng=rng).play()

    assert history[2] == ("D", "C")  # the accident: A defects once, unprovoked
    # Round 3 is a one-round asymmetric transition: B saw A's round-2 defection
    # and triggers immediately, but A hasn't yet seen B defect (B was still
    # cooperating up through round 2), so A cooperates once more here.
    assert history[3] == ("C", "D")
    # By round 4, A has now seen B defect (round 3) and triggers too - from
    # here on neither side ever forgives again: permanent mutual defection.
    assert all(move == ("D", "D") for move in history[4:])


def test_tit_for_tat_falls_into_an_echo_instead_of_locking_or_recovering() -> None:
    # Same single forced accident as the grim_trigger test above.
    values = [0.9] * 4 + [0.1] + [0.9] * 20
    rng = ScriptedRandom(values)

    score_a, score_b, history = Match(TitForTat(), TitForTat(), rounds=10, noise=0.5, rng=rng).play()

    assert history[2] == ("D", "C")  # the same accident
    # TFT never settles into mutual defection - it keeps alternating exploitation
    # instead (the well-known "echo" effect), never both-D and never both-C again.
    for move in history[3:]:
        assert move in (("D", "C"), ("C", "D"))

    # And that echo still scores better than GrimTrigger's permanent mutual defection
    # would over the same rounds - forgiveness costs something (getting exploited in
    # turn) but not as much as never cooperating again.
    grim_score, _, _ = Match(GrimTrigger(), GrimTrigger(), rounds=10, noise=0.5, rng=ScriptedRandom(values)).play()
    assert score_a > grim_score
    assert score_b > grim_score
