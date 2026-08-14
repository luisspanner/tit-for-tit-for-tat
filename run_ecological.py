import json
import uuid
from pathlib import Path

from tournament.archive import archive_run
from tournament.classic_roster import build_classic_strategies as build_strategies
from tournament.ecological import EcologicalTournament
from tournament.visualization import render_line_chart

ROUNDS = 100
GENERATIONS = 100
SEED = 7
RESULTS_DIR = Path(__file__).parent / "results"


def main() -> None:
    strategies = build_strategies()
    eco = EcologicalTournament(strategies, rounds=ROUNDS, seed=SEED)
    history = eco.run(generations=GENERATIONS)

    names = [s.name for s in strategies]
    generation_indices = list(range(len(history)))
    series = {name: [gen[name] for gen in history] for name in names}

    render_line_chart(
        generation_indices, series, RESULTS_DIR / "ecological_trajectory.png",
        xlabel="generation", ylabel="population share",
    )
    (RESULTS_DIR / "ecological_summary.json").write_text(json.dumps(history, indent=2))
    archive_run(
        RESULTS_DIR, str(uuid.uuid4()), "ecological", ["ecological_trajectory.png", "ecological_summary.json"]
    )

    print(f"Ran {GENERATIONS} generations, starting from equal shares.")
    print("Final population shares:")
    for name, share in sorted(history[-1].items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {name:<22}{share:.4f}")


if __name__ == "__main__":
    main()
