import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from tournament.archive import archive_run
from tournament.classic_roster import CLASSIC_STRATEGY_FACTORIES, build_classic_strategies
from tournament.ecological import EcologicalTournament
from tournament.experiments import sweep_round_robin, sweep_spatial
from tournament.last_round_experiment import run_last_round_experiment
from tournament.llm_roster import build_llm_strategies
from tournament.reporting import write_results_csv, write_standings_json
from tournament.spatial import Grid
from tournament.strategies.base import Strategy
from tournament.tournament import Tournament
from tournament.visualization import render_generations_gif, render_line_chart

REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results"
PROMPTS_DIR = REPO_ROOT / "prompts"
CACHE_DIR = REPO_ROOT / "cache"
TRANSCRIPTS_PATH = RESULTS_DIR / "llm_transcripts.jsonl"

DEFAULT_ROUNDS = {"classic_round_robin": 100, "llm_round_robin": 20, "last_round_experiment": 20}
DEFAULT_LRE_REPEATS = 5
EXPERIMENTS = {
    "classic_round_robin",
    "llm_round_robin",
    "spatial",
    "noise_sweep",
    "ecological",
    "last_round_experiment",
}

NOISE_LEVELS = [0.0, 0.02, 0.05, 0.1, 0.2, 0.3]
SPATIAL_GRID_SIZE = 8
SPATIAL_GENERATIONS = 40
ECOLOGICAL_GENERATIONS = 100
SEED = 7


class RunAlreadyInProgress(Exception):
    pass


@dataclass
class RunState:
    run_id: str
    experiment: str
    loop: asyncio.AbstractEventLoop
    status: str = "running"  # running | done | error
    started_at: float = field(default_factory=time.time)
    events: list[dict] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)


RUNS: dict[str, RunState] = {}


def emit(run: RunState, event: dict) -> None:
    with run.lock:
        run.events.append(event)
        for q in run.subscribers:
            run.loop.call_soon_threadsafe(q.put_nowait, event)


def get_run(run_id: str) -> RunState | None:
    return RUNS.get(run_id)


def list_runs() -> list[dict]:
    return [
        {"run_id": r.run_id, "experiment": r.experiment, "status": r.status, "started_at": r.started_at}
        for r in sorted(RUNS.values(), key=lambda r: r.started_at, reverse=True)
    ]


def start_run(
    experiment: str,
    rounds: int | None,
    include_classics: bool,
    models: list[str] | None = None,
    repeats: int | None = None,
) -> RunState:
    if experiment not in EXPERIMENTS:
        raise ValueError(f"unknown experiment: {experiment}")
    if any(r.status == "running" for r in RUNS.values()):
        raise RunAlreadyInProgress("a run is already in progress")

    resolved_rounds = rounds if rounds is not None else DEFAULT_ROUNDS.get(experiment, 100)
    resolved_repeats = repeats if repeats is not None else DEFAULT_LRE_REPEATS
    run = RunState(run_id=str(uuid.uuid4()), experiment=experiment, loop=asyncio.get_running_loop())
    RUNS[run.run_id] = run

    thread = threading.Thread(
        target=_worker,
        args=(run, experiment, resolved_rounds, include_classics, models, resolved_repeats),
        daemon=True,
    )
    thread.start()
    return run


def _build_llm_only_roster(models: list[str] | None = None) -> list[Strategy]:
    system_prompt = (PROMPTS_DIR / "baseline.txt").read_text()
    strategies = build_llm_strategies(system_prompt, CACHE_DIR)
    if models is not None:
        strategies = [s for s in strategies if s.model_name in models]
    return strategies


def _append_transcript(
    run_id: str,
    strategy_a: str,
    strategy_b: str,
    result: dict,
    moves: list[tuple[int, str, str, str | None, str | None]],
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    line = {
        "run_id": run_id,
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "model_a": result["model_a"],
        "model_b": result["model_b"],
        "rounds": result["rounds"],
        "moves": moves,
        "score_a": result["score_a"],
        "score_b": result["score_b"],
        "timestamp": time.time(),
    }
    with TRANSCRIPTS_PATH.open("a") as f:
        f.write(json.dumps(line) + "\n")


def _run_round_robin(
    run: RunState, experiment: str, rounds: int, include_classics: bool, models: list[str] | None
) -> None:
    if experiment == "classic_round_robin":
        strategies = build_classic_strategies()
    else:
        strategies = _build_llm_only_roster(models)
        if include_classics:
            strategies = build_classic_strategies() + strategies

    if not strategies:
        raise ValueError("No strategies configured for this experiment - check provider env vars.")

    tournament = Tournament(strategies, rounds=rounds)
    match_state = {"is_llm": False, "moves": []}

    def on_match_start(a: str, b: str, model_a: str | None, model_b: str | None) -> None:
        match_state["is_llm"] = model_a is not None or model_b is not None
        match_state["moves"] = []
        emit(run, {"type": "match_start", "strategy_a": a, "strategy_b": b, "model_a": model_a, "model_b": model_b})

    def on_round(
        a: str, b: str, round_index: int, move_a: str, move_b: str, reason_a: str | None, reason_b: str | None
    ) -> None:
        if not match_state["is_llm"]:
            return
        match_state["moves"].append((round_index, move_a, move_b, reason_a, reason_b))
        emit(
            run,
            {
                "type": "round",
                "strategy_a": a,
                "strategy_b": b,
                "round_index": round_index,
                "move_a": move_a,
                "move_b": move_b,
                "reason_a": reason_a,
                "reason_b": reason_b,
            },
        )

    def on_match_end(a: str, b: str, result: dict) -> None:
        emit(run, {"type": "match_end", "strategy_a": a, "strategy_b": b, "result": result})
        if match_state["is_llm"]:
            _append_transcript(run.run_id, a, b, result, match_state["moves"])

    def on_match_error(a: str, b: str, exc: Exception) -> None:
        emit(run, {"type": "match_error", "strategy_a": a, "strategy_b": b, "error": str(exc), "error_type": type(exc).__name__})

    results = tournament.play(
        on_match_start=on_match_start,
        on_round=on_round,
        on_match_end=on_match_end,
        on_match_error=on_match_error,
    )
    standings = tournament.standings(results)
    write_results_csv(results, RESULTS_DIR / "matches.csv")
    write_standings_json(standings, RESULTS_DIR / "standings.json")
    archive_run(RESULTS_DIR, run.run_id, run.experiment, ["matches.csv", "standings.json"])


def _run_spatial(run: RunState) -> None:
    grid = Grid(size=SPATIAL_GRID_SIZE, strategy_factories=CLASSIC_STRATEGY_FACTORIES, seed=SEED)
    generations = [grid.strategy_names()]
    counts_by_generation = [grid.strategy_counts()]
    for _ in range(SPATIAL_GENERATIONS):
        grid.step()
        generations.append(grid.strategy_names())
        counts_by_generation.append(grid.strategy_counts())

    render_generations_gif(
        generations,
        strategy_names=list(CLASSIC_STRATEGY_FACTORIES),
        gif_path=RESULTS_DIR / "spatial_evolution.gif",
        legend_path=RESULTS_DIR / "spatial_legend.json",
    )
    summary = [{"generation": i, "counts": counts} for i, counts in enumerate(counts_by_generation)]
    (RESULTS_DIR / "spatial_summary.json").write_text(json.dumps(summary, indent=2))
    archive_run(
        RESULTS_DIR,
        run.run_id,
        run.experiment,
        ["spatial_evolution.gif", "spatial_legend.json", "spatial_summary.json"],
    )


def _run_noise_sweep(run: RunState) -> None:
    roundrobin_by_noise = sweep_round_robin(
        build_classic_strategies, rounds=100, noise_levels=NOISE_LEVELS, seed=SEED
    )
    spatial_by_noise = sweep_spatial(
        size=SPATIAL_GRID_SIZE,
        strategy_factories=CLASSIC_STRATEGY_FACTORIES,
        generations=SPATIAL_GENERATIONS,
        noise_levels=NOISE_LEVELS,
        seed=SEED,
    )
    strategy_names = list(CLASSIC_STRATEGY_FACTORIES)

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
        run.run_id,
        run.experiment,
        ["noise_sweep_roundrobin.png", "noise_sweep_spatial.png", "noise_sweep_summary.json"],
    )


def _run_ecological(run: RunState) -> None:
    strategies = build_classic_strategies()
    eco = EcologicalTournament(strategies, rounds=100, seed=SEED)
    history = eco.run(generations=ECOLOGICAL_GENERATIONS)

    names = [s.name for s in strategies]
    generation_indices = list(range(len(history)))
    series = {name: [gen[name] for gen in history] for name in names}

    render_line_chart(
        generation_indices, series, RESULTS_DIR / "ecological_trajectory.png",
        xlabel="generation", ylabel="population share",
    )
    (RESULTS_DIR / "ecological_summary.json").write_text(json.dumps(history, indent=2))
    archive_run(
        RESULTS_DIR, run.run_id, run.experiment, ["ecological_trajectory.png", "ecological_summary.json"]
    )


def _run_last_round_experiment(run: RunState, rounds: int, repeats: int, models: list[str] | None) -> None:
    system_prompt = (PROMPTS_DIR / "baseline.txt").read_text()

    def on_repeat_start(model: str, opponent: str, repeat: int) -> None:
        emit(run, {"type": "lre_repeat_start", "model": model, "opponent": opponent, "repeat": repeat})

    def on_repeat_end(model: str, opponent: str, repeat: int, moves: list[str]) -> None:
        emit(
            run,
            {"type": "lre_repeat_end", "model": model, "opponent": opponent, "repeat": repeat, "moves": moves},
        )

    def on_model_done(model: str, result: dict) -> None:
        emit(run, {"type": "lre_model_done", "model": model, "result": result})

    summary = run_last_round_experiment(
        system_prompt,
        CACHE_DIR,
        rounds=rounds,
        repeats=repeats,
        models=models,
        on_repeat_start=on_repeat_start,
        on_repeat_end=on_repeat_end,
        on_model_done=on_model_done,
    )
    if not summary:
        raise ValueError("No strategies configured for this experiment - check provider env vars.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "last_round_experiment.json").write_text(json.dumps(summary, indent=2))

    series = {}
    round_indices = list(range(rounds))
    for model, result in summary.items():
        series[f"{model}_told"] = result["told"]["cooperation_by_round"]
        series[f"{model}_untold"] = result["untold"]["cooperation_by_round"]
    render_line_chart(
        round_indices, series, RESULTS_DIR / "last_round_cooperation.png",
        xlabel="round", ylabel="cooperation rate",
    )
    archive_run(
        RESULTS_DIR, run.run_id, run.experiment, ["last_round_experiment.json", "last_round_cooperation.png"]
    )


def _worker(
    run: RunState,
    experiment: str,
    rounds: int,
    include_classics: bool,
    models: list[str] | None,
    repeats: int,
) -> None:
    emit(run, {"type": "run_start", "experiment": experiment, "rounds": rounds})
    try:
        if experiment in ("classic_round_robin", "llm_round_robin"):
            _run_round_robin(run, experiment, rounds, include_classics, models)
        elif experiment == "spatial":
            _run_spatial(run)
        elif experiment == "noise_sweep":
            _run_noise_sweep(run)
        elif experiment == "ecological":
            _run_ecological(run)
        elif experiment == "last_round_experiment":
            _run_last_round_experiment(run, rounds, repeats, models)
        run.status = "done"
        emit(run, {"type": "run_complete"})
    except Exception as exc:
        run.status = "error"
        emit(run, {"type": "run_error", "error": str(exc)})
