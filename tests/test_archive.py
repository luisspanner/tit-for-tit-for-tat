import json
from pathlib import Path

from tournament.archive import archive_run, list_archived_runs


def test_archive_run_copies_existing_files_into_run_subfolder(tmp_path: Path) -> None:
    (tmp_path / "standings.json").write_text('{"a": 1}')
    (tmp_path / "matches.csv").write_text("strategy_a,strategy_b\n")

    archive_dir = archive_run(tmp_path, "abc123", "classic_round_robin", ["standings.json", "matches.csv", "missing.json"])

    assert archive_dir == tmp_path / "runs" / "abc123"
    assert (archive_dir / "standings.json").read_text() == '{"a": 1}'
    assert (archive_dir / "matches.csv").read_text() == "strategy_a,strategy_b\n"
    assert not (archive_dir / "missing.json").exists()


def test_archive_run_writes_manifest(tmp_path: Path) -> None:
    (tmp_path / "standings.json").write_text("{}")

    archive_dir = archive_run(tmp_path, "abc123", "classic_round_robin", ["standings.json", "missing.json"])

    manifest = json.loads((archive_dir / "manifest.json").read_text())
    assert manifest["run_id"] == "abc123"
    assert manifest["experiment"] == "classic_round_robin"
    assert manifest["files"] == ["standings.json"]
    assert isinstance(manifest["archived_at"], float)


def test_archive_run_does_not_touch_the_flat_latest_files(tmp_path: Path) -> None:
    (tmp_path / "standings.json").write_text('{"a": 1}')

    archive_run(tmp_path, "abc123", "classic_round_robin", ["standings.json"])

    assert (tmp_path / "standings.json").read_text() == '{"a": 1}'


def test_list_archived_runs_returns_sorted_by_recency(tmp_path: Path) -> None:
    older = tmp_path / "runs" / "older"
    newer = tmp_path / "runs" / "newer"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "manifest.json").write_text(
        json.dumps({"run_id": "older", "experiment": "classic_round_robin", "archived_at": 100.0, "files": []})
    )
    (newer / "manifest.json").write_text(
        json.dumps({"run_id": "newer", "experiment": "classic_round_robin", "archived_at": 200.0, "files": []})
    )

    runs = list_archived_runs(tmp_path)

    assert [r["run_id"] for r in runs] == ["newer", "older"]


def test_list_archived_runs_with_no_runs_dir_returns_empty(tmp_path: Path) -> None:
    assert list_archived_runs(tmp_path) == []
