from tournament.strategies.base import RoundContext
from tournament.strategies.classic import (
    AlwaysCooperate,
    AlwaysDefect,
    EndgameDefector,
    GenerousTitForTat,
    GrimTrigger,
    Joss,
    Pavlov,
    RandomStrategy,
    TitForTat,
)


def test_tit_for_tat_cooperates_on_first_move() -> None:
    assert TitForTat().move([]) == "C"


def test_tit_for_tat_copies_opponents_last_move() -> None:
    tft = TitForTat()
    assert tft.move([("C", "D")]) == "D"
    assert tft.move([("C", "C")]) == "C"
    assert tft.move([("C", "C"), ("C", "D")]) == "D"


def test_tit_for_tat_hand_computed_sequence() -> None:
    # Opponent plays C, D, D, C -> TFT should play C, C, D, D
    tft = TitForTat()
    history: list[tuple[str, str]] = []
    opponent_moves = ["C", "D", "D", "C"]
    expected_tft_moves = ["C", "C", "D", "D"]

    actual_tft_moves = []
    for opponent_move in opponent_moves:
        tft_move = tft.move(history)
        actual_tft_moves.append(tft_move)
        history.append((tft_move, opponent_move))

    assert actual_tft_moves == expected_tft_moves


def test_always_defect_always_defects() -> None:
    always_defect = AlwaysDefect()
    assert always_defect.move([]) == "D"
    assert always_defect.move([("D", "C")]) == "D"
    assert always_defect.move([("D", "D"), ("D", "C")]) == "D"


def test_always_cooperate_always_cooperates() -> None:
    always_cooperate = AlwaysCooperate()
    assert always_cooperate.move([]) == "C"
    assert always_cooperate.move([("C", "D")]) == "C"
    assert always_cooperate.move([("C", "D"), ("C", "D")]) == "C"


def test_grim_trigger_cooperates_until_opponent_defects_then_defects_forever() -> None:
    grim = GrimTrigger()
    assert grim.move([]) == "C"
    assert grim.move([("C", "C")]) == "C"
    assert grim.move([("C", "C"), ("C", "D")]) == "D"
    # Opponent goes back to cooperating - grim still never forgives.
    assert grim.move([("C", "C"), ("C", "D"), ("D", "C")]) == "D"


def test_pavlov_hand_computed_sequence_vs_always_defect() -> None:
    # Win-stay/lose-shift: every round against AlwaysDefect is a loss (payoff S or P),
    # so Pavlov alternates C, D, C, D, ... forever.
    pavlov = Pavlov()
    history: list[tuple[str, str]] = []
    expected_moves = ["C", "D", "C", "D"]

    actual_moves = []
    for _ in expected_moves:
        move = pavlov.move(history)
        actual_moves.append(move)
        history.append((move, "D"))

    assert actual_moves == expected_moves


def test_pavlov_stays_on_mutual_cooperation() -> None:
    pavlov = Pavlov()
    assert pavlov.move([("C", "C")]) == "C"
    assert pavlov.move([("C", "C"), ("C", "C")]) == "C"


def test_random_strategy_is_reproducible_with_same_seed() -> None:
    a = RandomStrategy(seed=42)
    b = RandomStrategy(seed=42)
    sequence_a = [a.move([]) for _ in range(20)]
    sequence_b = [b.move([]) for _ in range(20)]
    assert sequence_a == sequence_b
    assert "C" in sequence_a
    assert "D" in sequence_a


def test_random_strategy_p_cooperate_zero_always_defects() -> None:
    always_defect_random = RandomStrategy(p_cooperate=0.0, seed=1)
    assert all(always_defect_random.move([]) == "D" for _ in range(10))


def test_random_strategy_p_cooperate_one_always_cooperates() -> None:
    always_cooperate_random = RandomStrategy(p_cooperate=1.0, seed=1)
    assert all(always_cooperate_random.move([]) == "C" for _ in range(10))


def test_generous_tit_for_tat_with_zero_generosity_behaves_like_tit_for_tat() -> None:
    # generosity=0.0 -> never forgives -> identical to plain TFT.
    gtft = GenerousTitForTat(generosity=0.0)
    history: list[tuple[str, str]] = []
    opponent_moves = ["C", "D", "D", "C"]
    expected_moves = ["C", "C", "D", "D"]

    actual_moves = []
    for opponent_move in opponent_moves:
        move = gtft.move(history)
        actual_moves.append(move)
        history.append((move, opponent_move))

    assert actual_moves == expected_moves


def test_generous_tit_for_tat_with_full_generosity_always_cooperates() -> None:
    # generosity=1.0 -> always forgives a defection, and mirrors cooperation ->
    # equivalent to AlwaysCooperate regardless of what the opponent does.
    gtft = GenerousTitForTat(generosity=1.0, seed=1)
    assert gtft.move([]) == "C"
    assert gtft.move([("C", "D")]) == "C"
    assert gtft.move([("C", "D"), ("C", "D")]) == "C"


def test_joss_with_zero_defection_probability_behaves_like_tit_for_tat() -> None:
    joss = Joss(defection_probability=0.0)
    history: list[tuple[str, str]] = []
    opponent_moves = ["C", "D", "D", "C"]
    expected_moves = ["C", "C", "D", "D"]

    actual_moves = []
    for opponent_move in opponent_moves:
        move = joss.move(history)
        actual_moves.append(move)
        history.append((move, opponent_move))

    assert actual_moves == expected_moves


def test_joss_with_full_defection_probability_always_defects() -> None:
    # defection_probability=1.0 -> every time it would cooperate, it defects
    # instead, and it never softens an existing retaliation -> equivalent to
    # AlwaysDefect regardless of what the opponent does.
    joss = Joss(defection_probability=1.0, seed=1)
    assert joss.move([]) == "D"
    assert joss.move([("D", "C")]) == "D"
    assert joss.move([("D", "D")]) == "D"


def test_endgame_defector_behaves_like_tit_for_tat_without_last_round_context() -> None:
    endgame = EndgameDefector()
    history: list[tuple[str, str]] = []
    opponent_moves = ["C", "D", "D", "C"]
    expected_moves = ["C", "C", "D", "D"]

    actual_moves = []
    for i, opponent_move in enumerate(opponent_moves):
        context = RoundContext(round_index=i, total_rounds=len(opponent_moves) + 5)  # never the last round
        move = endgame.move(history, context)
        actual_moves.append(move)
        history.append((move, opponent_move))

    assert actual_moves == expected_moves


def test_endgame_defector_defects_on_the_last_round_regardless_of_history() -> None:
    endgame = EndgameDefector()
    # Even with a fully cooperative history, the last round is an unconditional defection.
    history = [("C", "C"), ("C", "C"), ("C", "C")]
    context = RoundContext(round_index=3, total_rounds=4)
    assert endgame.move(history, context) == "D"
