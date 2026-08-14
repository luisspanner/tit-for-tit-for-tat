import uuid
from pathlib import Path

from tournament.archive import archive_run
from tournament.classic_roster import build_classic_strategies
from tournament.llm_roster import build_llm_strategies
from tournament.reporting import write_results_csv, write_standings_json
from tournament.tournament import Tournament

ROUNDS = 100
RESULTS_DIR = Path(__file__).parent / "results"
PROMPTS_DIR = Path(__file__).parent / "prompts"
CACHE_DIR = Path(__file__).parent / "cache"


def build_strategies() -> list:
    strategies = build_classic_strategies()

    system_prompt = (PROMPTS_DIR / "baseline.txt").read_text()
    strategies.extend(build_llm_strategies(system_prompt, CACHE_DIR))

    return strategies


def main() -> None:
    strategies = build_strategies()
    tournament = Tournament(strategies, rounds=ROUNDS)
    results = tournament.play()
    standings = tournament.standings(results)

    write_results_csv(results, RESULTS_DIR / "matches.csv")
    write_standings_json(standings, RESULTS_DIR / "standings.json")
    archive_run(RESULTS_DIR, str(uuid.uuid4()), "run_v2_round_robin", ["matches.csv", "standings.json"])

    print(f"{'strategy':<20}{'total_score':>12}")
    for row in standings:
        print(f"{row['strategy']:<20}{row['total_score']:>12}")


if __name__ == "__main__":
    main()
