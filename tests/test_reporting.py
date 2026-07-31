import csv
import json
from pathlib import Path

from tournament.reporting import write_results_csv, write_standings_json


def test_write_results_csv_roundtrips(tmp_path: Path) -> None:
    results = [
        {"strategy_a": "tit_for_tat", "strategy_b": "always_defect", "rounds": 10, "score_a": 18, "score_b": 23},
    ]
    path = tmp_path / "nested" / "matches.csv"
    write_results_csv(results, path)

    with path.open() as f:
        rows = list(csv.DictReader(f))

    assert rows == [
        {"strategy_a": "tit_for_tat", "strategy_b": "always_defect", "rounds": "10", "score_a": "18", "score_b": "23"}
    ]


def test_write_standings_json_roundtrips(tmp_path: Path) -> None:
    standings = [
        {"strategy": "always_defect", "total_score": 42},
        {"strategy": "always_cooperate", "total_score": 10},
    ]
    path = tmp_path / "nested" / "standings.json"
    write_standings_json(standings, path)

    assert json.loads(path.read_text()) == standings
