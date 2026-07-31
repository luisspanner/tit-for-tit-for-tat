from tournament.match import Match
from tournament.strategies.classic import AlwaysDefect, TitForTat


def main() -> None:
    tit_for_tat = TitForTat()
    always_defect = AlwaysDefect()

    match = Match(tit_for_tat, always_defect, rounds=100)
    score_tft, score_defect, _ = match.play()

    print(f"{tit_for_tat.name}: {score_tft}")
    print(f"{always_defect.name}: {score_defect}")


if __name__ == "__main__":
    main()
