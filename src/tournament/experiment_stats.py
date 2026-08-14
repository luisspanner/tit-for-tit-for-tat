import math
from typing import Callable

from tournament.strategies.base import Strategy
from tournament.strategies.classic import AlwaysCooperate, TitForTat

DEFAULT_OPPONENT_FACTORIES: list[Callable[[], Strategy]] = [TitForTat, AlwaysCooperate]


def two_proportion_z(defect_a: int, total_a: int, defect_b: int, total_b: int) -> float | None:
    """Standard two-proportion z-test statistic; None when either sample is empty."""
    if total_a == 0 or total_b == 0:
        return None
    p_a = defect_a / total_a
    p_b = defect_b / total_b
    p_pool = (defect_a + defect_b) / (total_a + total_b)
    variance = p_pool * (1 - p_pool) * (1 / total_a + 1 / total_b)
    if variance == 0:
        return None
    return (p_a - p_b) / math.sqrt(variance)


def two_tailed_p_value(z: float) -> float:
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
