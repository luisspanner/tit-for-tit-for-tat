from tournament.match import Match
from tournament.strategies.classic import AlwaysDefect, TitForTat


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
