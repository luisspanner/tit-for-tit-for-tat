import json
import shutil
import time
from pathlib import Path


def archive_run(results_dir: Path, run_id: str, experiment: str, filenames: list[str]) -> Path:
    """Copy whichever of `filenames` currently exist under `results_dir` into
    `results_dir/runs/<run_id>/`, alongside a manifest.json. Leaves the
    "latest" flat files in `results_dir` untouched - this only adds history,
    it never changes what the flat files mean."""
    archive_dir = results_dir / "runs" / run_id
    archive_dir.mkdir(parents=True, exist_ok=True)

    present = []
    for name in filenames:
        source = results_dir / name
        if source.exists():
            shutil.copy2(source, archive_dir / name)
            present.append(name)

    manifest = {
        "run_id": run_id,
        "experiment": experiment,
        "archived_at": time.time(),
        "files": present,
    }
    (archive_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    return archive_dir


def list_archived_runs(results_dir: Path) -> list[dict]:
    """Read every results_dir/runs/*/manifest.json, sorted newest-first."""
    runs_dir = results_dir / "runs"
    if not runs_dir.exists():
        return []

    manifests = []
    for manifest_path in runs_dir.glob("*/manifest.json"):
        manifests.append(json.loads(manifest_path.read_text()))

    return sorted(manifests, key=lambda m: m["archived_at"], reverse=True)
