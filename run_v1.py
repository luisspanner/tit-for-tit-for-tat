from pathlib import Path

from tournament.llm_roster import build_llm_strategies
from tournament.match import Match
from tournament.strategies.classic import TitForTat

ROUNDS = 10
PROMPTS_DIR = Path(__file__).parent / "prompts"
CACHE_DIR = Path(__file__).parent / "cache"


def main() -> None:
    system_prompt = (PROMPTS_DIR / "baseline.txt").read_text()
    llm_strategies = build_llm_strategies(system_prompt, CACHE_DIR)

    if not llm_strategies:
        print("No LLM providers configured - nothing to run.")
        return

    for llm_strategy in llm_strategies:
        tit_for_tat = TitForTat()
        match = Match(llm_strategy, tit_for_tat, rounds=ROUNDS)
        score_llm, score_tft, history = match.play()

        print(f"\n=== {llm_strategy.name} ({llm_strategy.model_name}) vs tit_for_tat ===")
        for i, (mine, theirs) in enumerate(history):
            print(f"Round {i + 1}: {llm_strategy.name}={mine}, tit_for_tat={theirs}")

        print(f"\n{llm_strategy.name}: {score_llm}")
        print(f"{tit_for_tat.name}: {score_tft}")


if __name__ == "__main__":
    main()
