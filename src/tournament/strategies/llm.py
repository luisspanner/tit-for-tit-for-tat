from tournament.cache import DiskCache, cache_key
from tournament.llm_client import LLMClient
from tournament.strategies.base import Move


def render_history(history: list[tuple[Move, Move]]) -> str:
    if not history:
        rounds = "No rounds have been played yet. This is round 1."
    else:
        lines = [f"Round {i + 1}: You: {mine}, Opponent: {theirs}" for i, (mine, theirs) in enumerate(history)]
        rounds = "History so far:\n" + "\n".join(lines)
    return f"{rounds}\n\nWhat is your move? Respond with exactly one character: C or D."


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

    def move(self, history: list[tuple[Move, Move]]) -> Move:
        key = cache_key(self.system_prompt, history)

        if self.cache is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return parse_move(cached)

        raw = self.client.complete(self.system_prompt, render_history(history))

        if self.cache is not None:
            self.cache.set(key, raw)

        return parse_move(raw)
