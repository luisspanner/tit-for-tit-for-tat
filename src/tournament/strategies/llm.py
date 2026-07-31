from tournament.cache import DiskCache, cache_key
from tournament.llm_client import LLMClient
from tournament.strategies.base import Move, RoundContext


def render_history(history: list[tuple[Move, Move]], context: RoundContext | None = None) -> str:
    if not history:
        rounds = "No rounds have been played yet. This is round 1."
    else:
        lines = [f"Round {i + 1}: You: {mine}, Opponent: {theirs}" for i, (mine, theirs) in enumerate(history)]
        rounds = "History so far:\n" + "\n".join(lines)

    last_round_notice = ""
    if context is not None and context.is_last_round:
        last_round_notice = " This is the final round - there will be no more rounds after this one."

    return f"{rounds}\n\nWhat is your move?{last_round_notice} Respond with exactly one character: C or D."


def parse_move(raw: str) -> Move:
    text = raw.strip().upper()
    if text.startswith("C") or "COOPERATE" in text:
        return "C"
    if text.startswith("D") or "DEFECT" in text:
        return "D"
    raise ValueError(f"Could not parse move from LLM response: {raw!r}")


class LLMStrategy:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        client: LLMClient,
        cache: DiskCache | None = None,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.client = client
        self.cache = cache

    def move(self, history: list[tuple[Move, Move]], context: RoundContext | None = None) -> Move:
        is_last_round = context is not None and context.is_last_round
        key = cache_key(self.system_prompt, history, is_last_round=is_last_round)

        if self.cache is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return parse_move(cached)

        raw = self.client.complete(self.system_prompt, render_history(history, context))

        if self.cache is not None:
            self.cache.set(key, raw)

        return parse_move(raw)
