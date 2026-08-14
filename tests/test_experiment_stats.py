import pytest

from tournament.experiment_stats import two_proportion_z, two_tailed_p_value


def test_two_proportion_z_matches_hand_computed_value() -> None:
    # p_a = 8/10 = 0.8, p_b = 2/10 = 0.2, p_pool = 0.5
    # variance = 0.5*0.5*(1/10+1/10) = 0.05, sqrt = 0.2236..., z = 0.6/0.2236 = 2.683...
    z = two_proportion_z(8, 10, 2, 10)
    assert z is not None
    assert z == pytest.approx(2.683, abs=0.01)


def test_two_proportion_z_returns_none_for_empty_sample() -> None:
    assert two_proportion_z(0, 0, 5, 10) is None


def test_two_tailed_p_value_of_zero_is_one() -> None:
    assert two_tailed_p_value(0.0) == pytest.approx(1.0)


def test_two_tailed_p_value_shrinks_as_z_grows() -> None:
    assert two_tailed_p_value(3.0) < two_tailed_p_value(1.0) < two_tailed_p_value(0.5)
