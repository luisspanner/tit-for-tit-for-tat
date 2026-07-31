import os
from pathlib import Path

from tournament.reporting import write_results_csv, write_standings_json
from tournament.strategies.classic import (
    AlwaysCooperate,
    AlwaysDefect,
    GrimTrigger,
    Pavlov,
    RandomStrategy,
    TitForTat,
)
from tournament.tournament import Tournament

ROUNDS = 100
RESULTS_DIR = Path(__file__).parent / "results"
PROMPTS_DIR = Path(__file__).parent / "prompts"
CACHE_DIR = Path(__file__).parent / "cache"


def build_strategies() -> list:
    strategies = [
        TitForTat(),
        AlwaysDefect(),
        AlwaysCooperate(),
        GrimTrigger(),
        Pavlov(),
        RandomStrategy(seed=42),
    ]

    if os.environ.get("ANTHROPIC_API_KEY"):
        from tournament.cache import DiskCache
        from tournament.llm_client import AnthropicLLMClient
        from tournament.strategies.llm import LLMStrategy

        system_prompt = (PROMPTS_DIR / "baseline.txt").read_text()
        cache = DiskCache(CACHE_DIR / "baseline.json")
        strategies.append(
            LLMStrategy(name="llm_baseline", system_prompt=system_prompt, client=AnthropicLLMClient(), cache=cache)
        )
    else:
        print("ANTHROPIC_API_KEY not set - running classic strategies only, no LLM strategy included.\n")

    return strategies


def main() -> None:
    strategies = build_strategies()
    tournament = Tournament(strategies, rounds=ROUNDS)
    results = tournament.play()
    standings = tournament.standings(results)

    write_results_csv(results, RESULTS_DIR / "matches.csv")
    write_standings_json(standings, RESULTS_DIR / "standings.json")

    print(f"{'strategy':<20}{'total_score':>12}")
    for row in standings:
        print(f"{row['strategy']:<20}{row['total_score']:>12}")


if __name__ == "__main__":
    main()
