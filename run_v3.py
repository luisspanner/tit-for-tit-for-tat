import json
import uuid
from pathlib import Path

from tournament.archive import archive_run
from tournament.classic_roster import CLASSIC_STRATEGY_FACTORIES as STRATEGY_FACTORIES
from tournament.spatial import Grid
from tournament.visualization import render_generations_gif

GRID_SIZE = 8
GENERATIONS = 40
SEED = 7
RESULTS_DIR = Path(__file__).parent / "results"


def main() -> None:
    grid = Grid(size=GRID_SIZE, strategy_factories=STRATEGY_FACTORIES, seed=SEED)

    generations = [grid.strategy_names()]
    counts_by_generation = [grid.strategy_counts()]

    for _ in range(GENERATIONS):
        grid.step()
        generations.append(grid.strategy_names())
        counts_by_generation.append(grid.strategy_counts())

    render_generations_gif(
        generations,
        strategy_names=list(STRATEGY_FACTORIES),
        gif_path=RESULTS_DIR / "spatial_evolution.gif",
        legend_path=RESULTS_DIR / "spatial_legend.json",
    )

    summary = [{"generation": i, "counts": counts} for i, counts in enumerate(counts_by_generation)]
    (RESULTS_DIR / "spatial_summary.json").write_text(json.dumps(summary, indent=2))
    archive_run(
        RESULTS_DIR,
        str(uuid.uuid4()),
        "spatial",
        ["spatial_evolution.gif", "spatial_legend.json", "spatial_summary.json"],
    )

    print(f"Ran {GENERATIONS} generations on a {GRID_SIZE}x{GRID_SIZE} grid.")
    print("Final strategy counts:", counts_by_generation[-1])
    print(f"GIF written to {RESULTS_DIR / 'spatial_evolution.gif'}")


if __name__ == "__main__":
    main()
