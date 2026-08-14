import csv
import json
from pathlib import Path


def write_results_csv(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["strategy_a", "strategy_b", "rounds", "score_a", "score_b", "model_a", "model_b"]
        )
        writer.writeheader()
        writer.writerows(results)


def write_standings_json(standings: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(standings, indent=2))
