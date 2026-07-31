from tournament.payoff import score_round
from tournament.strategies.base import Move, Strategy


class Match:
    def __init__(self, strategy_a: Strategy, strategy_b: Strategy, rounds: int = 100) -> None:
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.rounds = rounds

    def play(self) -> tuple[int, int, list[tuple[Move, Move]]]:
        history_a: list[tuple[Move, Move]] = []
        history_b: list[tuple[Move, Move]] = []
        score_a = 0
        score_b = 0

        for _ in range(self.rounds):
            move_a = self.strategy_a.move(history_a)
            move_b = self.strategy_b.move(history_b)

            round_score_a, round_score_b = score_round(move_a, move_b)
            score_a += round_score_a
            score_b += round_score_b

            history_a.append((move_a, move_b))
            history_b.append((move_b, move_a))

        return score_a, score_b, history_a
