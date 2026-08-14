import asyncio
import csv
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tournament.archive import list_archived_runs
from tournament.llm_roster import configured_model_names
from tournament.model_catalog import MODEL_SIZE_BILLIONS
from tournament.webapp import runs as runs_module
from tournament.webapp.runs import RESULTS_DIR, RunAlreadyInProgress, get_run, list_runs, start_run

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Iterated Prisoner's Dilemma Tournament")
app.mount("/results", StaticFiles(directory=RESULTS_DIR, check_dir=False), name="results")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class StartRunRequest(BaseModel):
    experiment: str
    rounds: int | None = None
    include_classics: bool = False
    models: list[str] | None = None
    repeats: int | None = None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/runs")
async def create_run(body: StartRunRequest):
    try:
        run = start_run(body.experiment, body.rounds, body.include_classics, body.models, body.repeats)
    except RunAlreadyInProgress:
        raise HTTPException(status_code=409, detail="a run is already in progress")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"run_id": run.run_id, "experiment": run.experiment}


@app.get("/api/runs")
def get_runs():
    return list_runs()


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str):
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run_id")

    async def gen():
        with run.lock:
            queue: asyncio.Queue = asyncio.Queue()
            run.subscribers.add(queue)
            backlog = list(run.events)
        for event in backlog:
            yield _sse(event)
        if run.status != "running":
            return
        try:
            while True:
                event = await queue.get()
                yield _sse(event)
                if event["type"] in ("run_complete", "run_error"):
                    return
        finally:
            with run.lock:
                run.subscribers.discard(queue)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/standings")
def get_standings():
    data = _read_json(runs_module.RESULTS_DIR / "standings.json")
    if data is None:
        raise HTTPException(status_code=404, detail="no standings yet - run a round robin first")
    return data


@app.get("/api/matches")
def get_matches(model: str | None = None):
    path = runs_module.RESULTS_DIR / "matches.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no matches yet - run a round robin first")
    with path.open() as f:
        rows = list(csv.DictReader(f))
    if model:
        rows = [r for r in rows if r["model_a"] == model or r["model_b"] == model]
    return rows


@app.get("/api/spatial")
def get_spatial():
    summary = _read_json(runs_module.RESULTS_DIR / "spatial_summary.json")
    legend = _read_json(runs_module.RESULTS_DIR / "spatial_legend.json")
    if summary is None:
        raise HTTPException(status_code=404, detail="no spatial run yet")
    return {"summary": summary, "legend": legend, "seed": runs_module.SEED}


@app.get("/api/noise-sweep")
def get_noise_sweep():
    data = _read_json(runs_module.RESULTS_DIR / "noise_sweep_summary.json")
    if data is None:
        raise HTTPException(status_code=404, detail="no noise sweep run yet")
    return data


@app.get("/api/ecological")
def get_ecological():
    data = _read_json(runs_module.RESULTS_DIR / "ecological_summary.json")
    if data is None:
        raise HTTPException(status_code=404, detail="no ecological run yet")
    return data


@app.get("/api/last-round-experiment")
def get_last_round_experiment():
    data = _read_json(runs_module.RESULTS_DIR / "last_round_experiment.json")
    if data is None:
        raise HTTPException(status_code=404, detail="no last-round experiment run yet")
    return data


@app.get("/api/runs/history")
def get_runs_history():
    return list_archived_runs(runs_module.RESULTS_DIR)


@app.get("/api/model-catalog")
def get_model_catalog():
    return MODEL_SIZE_BILLIONS


@app.get("/api/configured-models")
def get_configured_models():
    return configured_model_names()


def _read_transcripts() -> list[dict]:
    path = runs_module.TRANSCRIPTS_PATH
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


@app.get("/api/transcripts")
def list_transcripts(full: bool = False, run_id: str | None = None):
    entries = _read_transcripts()
    result = []
    for i, e in enumerate(entries):
        if run_id is not None and e.get("run_id") != run_id:
            continue
        row = {
            "match_key": f"{e['strategy_a']}__{e['strategy_b']}__{i}",
            "strategy_a": e["strategy_a"],
            "strategy_b": e["strategy_b"],
            "model_a": e["model_a"],
            "model_b": e["model_b"],
            "score_a": e["score_a"],
            "score_b": e["score_b"],
            "timestamp": e["timestamp"],
        }
        if full:
            row["moves"] = e["moves"]
        result.append(row)
    return result


@app.get("/api/transcripts/{match_key}")
def get_transcript(match_key: str):
    entries = _read_transcripts()
    for i, e in enumerate(entries):
        if f"{e['strategy_a']}__{e['strategy_b']}__{i}" == match_key:
            return e
    raise HTTPException(status_code=404, detail="unknown match_key")
