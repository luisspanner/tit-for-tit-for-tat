from pathlib import Path

from tournament.cache import DiskCache
from tournament.llm_client import AnthropicLLMClient
from tournament.match import Match
from tournament.strategies.classic import TitForTat
from tournament.strategies.llm import LLMStrategy

ROUNDS = 10
PROMPTS_DIR = Path(__file__).parent / "prompts"
CACHE_DIR = Path(__file__).parent / "cache"


def main() -> None:
    system_prompt = (PROMPTS_DIR / "baseline.txt").read_text()
    cache = DiskCache(CACHE_DIR / "baseline.json")
    client = AnthropicLLMClient()

    llm_strategy = LLMStrategy(name="llm_baseline", system_prompt=system_prompt, client=client, cache=cache)
    tit_for_tat = TitForTat()

    match = Match(llm_strategy, tit_for_tat, rounds=ROUNDS)
    score_llm, score_tft, history = match.play()

    for i, (mine, theirs) in enumerate(history):
        print(f"Round {i + 1}: llm_baseline={mine}, tit_for_tat={theirs}")

    print(f"\n{llm_strategy.name}: {score_llm}")
    print(f"{tit_for_tat.name}: {score_tft}")


if __name__ == "__main__":
    main()
