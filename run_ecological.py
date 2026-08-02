import json
from pathlib import Path

from tournament.ecological import EcologicalTournament
from tournament.strategies.classic import (
    AlwaysCooperate,
    AlwaysDefect,
    EndgameDefector,
    GenerousTitForTat,
    GrimTrigger,
    Joss,
    Pavlov,
    RandomStrategy,
    TitForTat,
)
from tournament.visualization import render_line_chart

ROUNDS = 100
GENERATIONS = 100
SEED = 7
RESULTS_DIR = Path(__file__).parent / "results"


def build_strategies() -> list:
    return [
        TitForTat(),
        AlwaysDefect(),
        AlwaysCooperate(),
        GrimTrigger(),
        Pavlov(),
        RandomStrategy(seed=42),
        GenerousTitForTat(seed=43),
        Joss(seed=44),
        EndgameDefector(),
    ]


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

    print(f"Ran {GENERATIONS} generations, starting from equal shares.")
    print("Final population shares:")
    for name, share in sorted(history[-1].items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {name:<22}{share:.4f}")


if __name__ == "__main__":
    main()
