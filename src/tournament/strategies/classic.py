from tournament.strategies.base import Move


class TitForTat:
    name = "tit_for_tat"

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        if not history:
            return "C"
        _, opponent_last = history[-1]
        return opponent_last


class AlwaysDefect:
    name = "always_defect"

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        return "D"
