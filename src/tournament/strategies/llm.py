from tournament.cache import DiskCache, cache_key
from tournament.llm_client import LLMClient
from tournament.strategies.base import Move, RoundContext


def render_history(
    history: list[tuple[Move, Move]],
    context: RoundContext | None = None,
    announce_last_round: bool = True,
) -> str:
    if not history:
        rounds = "No rounds have been played yet. This is round 1."
    else:
        lines = [f"Round {i + 1}: You: {mine}, Opponent: {theirs}" for i, (mine, theirs) in enumerate(history)]
        rounds = "History so far:\n" + "\n".join(lines)

    last_round_notice = ""
    if announce_last_round and context is not None and context.is_last_round:
        last_round_notice = " This is the final round - there will be no more rounds after this one."

    return (
        f"{rounds}\n\nWhat is your move?{last_round_notice} "
        "Respond in the format: <C or D> - <one-sentence reason>."
    )


def parse_move(raw: str) -> Move:
    text = raw.strip().upper()
    if text.startswith("C") or "COOPERATE" in text:
        return "C"
    if text.startswith("D") or "DEFECT" in text:
        return "D"
    raise ValueError(f"Could not parse move from LLM response: {raw!r}")


def parse_move_and_reason(raw: str) -> tuple[Move, str | None]:
    move = parse_move(raw)
    _, _, reason = raw.strip().partition(" - ")
    reason = reason.strip()
    return move, reason or None


class LLMStrategy:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        client: LLMClient,
        cache: DiskCache | None = None,
        model_name: str | None = None,
        announce_last_round: bool = True,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.client = client
        self.cache = cache
        self.model_name = model_name
        self.announce_last_round = announce_last_round
        self.last_reasoning: str | None = None

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        is_last_round = context is not None and context.is_last_round and self.announce_last_round
        key = cache_key(self.system_prompt, history, is_last_round=is_last_round, model=self.model_name or "")

        if self.cache is not None:
            cached = self.cache.get(key)
            if cached is not None:
                move, reason = parse_move_and_reason(cached)
                self.last_reasoning = reason
                return move

        raw = self.client.complete(
            self.system_prompt, render_history(history, context, announce_last_round=self.announce_last_round)
        )
        move, reason = parse_move_and_reason(raw)
        self.last_reasoning = reason

        if self.cache is not None:
            self.cache.set(key, raw)

        return move
