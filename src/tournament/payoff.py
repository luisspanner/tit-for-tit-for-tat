"""Standard iterated Prisoner's Dilemma payoff matrix."""

T = 5  # Temptation: I defect, opponent cooperates
R = 3  # Reward: both cooperate
P = 1  # Punishment: both defect
S = 0  # Sucker: I cooperate, opponent defects

_PAYOFF = {
    ("C", "C"): (R, R),
    ("C", "D"): (S, T),
    ("D", "C"): (T, S),
    ("D", "D"): (P, P),
}


def validate_payoffs() -> None:
    if not (T > R > P > S):
        raise ValueError(f"Payoff matrix must satisfy T > R > P > S, got T={T}, R={R}, P={P}, S={S}")
    if not (2 * R > T + S):
        raise ValueError(f"Payoff matrix must satisfy 2R > T + S, got 2R={2 * R}, T+S={T + S}")


def score_round(move_a: str, move_b: str) -> tuple[int, int]:
    return _PAYOFF[(move_a, move_b)]


validate_payoffs()
