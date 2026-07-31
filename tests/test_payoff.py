import pytest

from tournament.payoff import P, R, S, T, score_round, validate_payoffs


def test_default_payoffs_are_valid() -> None:
    validate_payoffs()


def test_score_round_matches_matrix() -> None:
    assert score_round("C", "C") == (R, R)
    assert score_round("C", "D") == (S, T)
    assert score_round("D", "C") == (T, S)
    assert score_round("D", "D") == (P, P)


def test_validate_rejects_broken_ordering(monkeypatch: pytest.MonkeyPatch) -> None:
    import tournament.payoff as payoff

    monkeypatch.setattr(payoff, "T", 1)
    monkeypatch.setattr(payoff, "R", 3)
    monkeypatch.setattr(payoff, "P", 1)
    monkeypatch.setattr(payoff, "S", 0)
    with pytest.raises(ValueError):
        payoff.validate_payoffs()


def test_validate_rejects_broken_reward_condition(monkeypatch: pytest.MonkeyPatch) -> None:
    import tournament.payoff as payoff

    monkeypatch.setattr(payoff, "T", 5)
    monkeypatch.setattr(payoff, "R", 2)
    monkeypatch.setattr(payoff, "P", 1)
    monkeypatch.setattr(payoff, "S", 0)
    with pytest.raises(ValueError):
        payoff.validate_payoffs()
