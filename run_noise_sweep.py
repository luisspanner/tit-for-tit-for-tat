import json
import uuid
from pathlib import Path

from tournament.archive import archive_run
from tournament.classic_roster import CLASSIC_STRATEGY_FACTORIES as STRATEGY_FACTORIES
from tournament.classic_roster import build_classic_strategies as build_strategies
from tournament.experiments import sweep_round_robin, sweep_spatial
from tournament.visualization import render_line_chart

NOISE_LEVELS = [0.0, 0.02, 0.05, 0.1, 0.2, 0.3]
ROUNDS = 100
GRID_SIZE = 8
GENERATIONS = 40
SEED = 7
RESULTS_DIR = Path(__file__).parent / "results"


def main() -> None:
    roundrobin_by_noise = sweep_round_robin(build_strategies, rounds=ROUNDS, noise_levels=NOISE_LEVELS, seed=SEED)
    spatial_by_noise = sweep_spatial(
        size=GRID_SIZE, strategy_factories=STRATEGY_FACTORIES, generations=GENERATIONS,
        noise_levels=NOISE_LEVELS, seed=SEED,
    )

    strategy_names = list(STRATEGY_FACTORIES)

    roundrobin_series = {name: [] for name in strategy_names}
    for noise in NOISE_LEVELS:
        totals = {row["strategy"]: row["total_score"] for row in roundrobin_by_noise[noise]}
        for name in strategy_names:
            roundrobin_series[name].append(totals[name])

    spatial_series = {name: [] for name in strategy_names}
    for noise in NOISE_LEVELS:
        counts = spatial_by_noise[noise]
        for name in strategy_names:
            spatial_series[name].append(counts[name])

    render_line_chart(
        NOISE_LEVELS, roundrobin_series, RESULTS_DIR / "noise_sweep_roundrobin.png",
        xlabel="noise rate", ylabel="total score",
    )
    render_line_chart(
        NOISE_LEVELS, spatial_series, RESULTS_DIR / "noise_sweep_spatial.png",
        xlabel="noise rate", ylabel="final cell count",
    )

    summary = {
        "noise_levels": NOISE_LEVELS,
        "round_robin": {str(noise): roundrobin_by_noise[noise] for noise in NOISE_LEVELS},
        "spatial": {str(noise): spatial_by_noise[noise] for noise in NOISE_LEVELS},
    }
    (RESULTS_DIR / "noise_sweep_summary.json").write_text(json.dumps(summary, indent=2))
    archive_run(
        RESULTS_DIR,
        str(uuid.uuid4()),
        "noise_sweep",
        ["noise_sweep_roundrobin.png", "noise_sweep_spatial.png", "noise_sweep_summary.json"],
    )

    print(f"{'strategy':<22}" + "".join(f"{noise:>10}" for noise in NOISE_LEVELS))
    for name in strategy_names:
        print(f"{name:<22}" + "".join(f"{v:>10}" for v in roundrobin_series[name]))


if __name__ == "__main__":
    main()
