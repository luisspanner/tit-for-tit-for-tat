from tournament.classic_roster import build_classic_strategies


def test_build_classic_strategies_returns_nine_distinct_named_strategies() -> None:
    strategies = build_classic_strategies()

    names = [s.name for s in strategies]
    assert len(names) == len(set(names)) == 9


def test_build_classic_strategies_returns_fresh_instances_each_call() -> None:
    first = build_classic_strategies()
    second = build_classic_strategies()

    assert first[0] is not second[0]
