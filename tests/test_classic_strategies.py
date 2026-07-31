from tournament.strategies.classic import AlwaysDefect, TitForTat


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
